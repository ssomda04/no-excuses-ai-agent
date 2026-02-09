import streamlit as st
from datetime import datetime, date
from dotenv import load_dotenv

from services.classifier import classify_excuse
from services.weather import get_weather
import db

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


def evaluate_time_excuse(exercise_time_str: str, excuse_text: str):
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
        exercise_end = time_obj((ex_hour + 1) % 24, ex_min)

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

            # 겹침 판정 (1시간 운동 기준)
            if exercise_start <= ev_time < exercise_end:
                return {"valid": True, "reason": "schedule_conflict"}

        # 겹치는 일정 없음 -> 거짓 핑계
        return {"valid": False, "reason": "claimed_time_but_no_conflict"}

    except Exception as e:
        # 캘린더 연동 실패시 판단 불가
        st.warning(f"⚠️ 캘린더 확인 불가: {str(e)}")
        return {"valid": None, "reason": "calendar_unavailable"}
    # ❌ 비 온다 했는데 실제로 안 옴 → 거짓 핑계
    if claimed_rain and not weather_fact["rain"]:
        return {
            "valid": False,
            "reason": "claimed_rain_but_no_rain"
        }

    # 🥶 너무 추운 날씨 → 합당
    if weather_fact["temp"] <= -5:
        return {
            "valid": True,
            "reason": "too_cold"
        }

    # 🌧️ 실제 비/눈
    if weather_fact["rain"] or weather_fact["snow"]:
        return {
            "valid": True,
            "reason": "actual_bad_weather"
        }

    return {
        "valid": True,
        "reason": "neutral_weather"
    }


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
    days = st.multiselect("운동 요일", ["월", "화", "수", "목", "금", "토", "일"])
    exercise_time = st.time_input("운동 시간")

    if st.button("저장하고 시작하기"):
        if not name or not days:
            st.warning("이름과 운동 요일은 필수입니다.")
        else:
            st.session_state.user = {
                "name": name,
                "plan": {
                    "days": days,
                    "time": exercise_time.strftime("%H:%M")
                }
            }
            # persist user and schedules
            user_id = db.ensure_user(name)
            st.session_state.user["id"] = user_id
            db.set_schedules(user_id, days, exercise_time.strftime("%H:%M"))
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
    st.write(f"- ⏰ 시간: {plan['time']}")
    st.divider()

    now = datetime.now()
    today = date.today()
    today_weekday = WEEKDAY_MAP[now.weekday()]
    is_exercise_day = today_weekday in plan["days"]

    exercise_time_today = datetime.strptime(
        f"{today} {plan['time']}",
        "%Y-%m-%d %H:%M"
    )

    if not is_exercise_day:
        st.info(f"📌 오늘은 운동 요일이 아니에요 ({today_weekday}).")

    elif now >= exercise_time_today and st.session_state.last_check_date != today:
        st.warning("⏰ 오늘 운동 시간이에요!")

        did_exercise = st.radio(
            "오늘 운동 하셨나요?",
            ["선택", "했어요", "못 했어요"]
        )

        if did_exercise == "했어요":
            st.success("🔥 오늘 운동 완료! 잘하셨어요.")
            st.session_state.last_check_date = today
            # save log
            user_id = st.session_state.user.get("id") or db.ensure_user(st.session_state.user.get("name", "unknown"))
            st.session_state.user["id"] = user_id
            db.add_exercise_log(user_id, today.isoformat(), True)

        elif did_exercise == "못 했어요":
            excuse = st.text_input("❓ 왜 못 하셨나요?")

            if excuse:
                st.subheader("🧠 AI 분석 결과")

                result = classify_excuse(excuse)
                excuse_type = result["excuse_type"]
                confidence = result["confidence"]
                reason = result["reason"]

                policy = EXCUSE_POLICY.get(excuse_type, "NEUTRAL_REFLECT")
                st.session_state.last_check_date = today

                # persist exercise log (did_exercise = False) and excuse
                user_id = st.session_state.user.get("id") or db.ensure_user(st.session_state.user.get("name", "unknown"))
                st.session_state.user["id"] = user_id
                log_id = db.add_exercise_log(user_id, today.isoformat(), False)

                st.write("📌 핑계 유형:", excuse_type)
                st.write("🔍 확신도:", round(confidence, 2))
                st.write("🧠 판단 근거:", reason)
                st.write("🤖 적용 정책:", policy)
                st.divider()

                # =======================
                # WEATHER_CHECK (핵심 수정)
                # =======================
                if policy == "WEATHER_CHECK":
                    weather_fact = get_weather_fact()
                    eval_result = evaluate_weather_excuse(excuse, weather_fact)

                    st.subheader("🌤️ 실제 날씨 분석")
                    st.write(f"- 상태: {weather_fact['desc']}")
                    st.write(f"- 기온: {weather_fact['temp']}°C")
                    st.divider()

                    # ❌ 거짓 핑계
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
                            "👉 이 핑계는 날씨로는 정당화되기 어려워요.\n\n"
                            "운동하러 가볼까요?"
                        )

                        # persist excuse log with judgment
                        db.add_excuse_log(log_id, excuse, excuse_type, confidence, reason, policy, eval_result.get("reason"))
                    # ✅ 합당한 날씨
                    else:
                        st.info(
                            "오늘은 날씨가 운동하기에 부담스러웠을 수 있어요."
                        )
                        st.success("🏠 추천: 실내 스트레칭 10분")
                        db.add_excuse_log(log_id, excuse, excuse_type, confidence, reason, policy, eval_result.get("reason"))

                # =======================
                # TIME_CHECK: 캘린더 기반 일정 확인
                # =======================
                elif policy == "TIME_CHECK":
                    time_eval = evaluate_time_excuse(plan['time'], excuse)

                    if time_eval["valid"] is None:
                        # 캘린더 연동 불가 또는 시간 관련 핑계 아님
                        st.warning("⏰ 일정 확인이 불가능하거나 시간 관련 사유가 아닙니다.")
                        db.add_excuse_log(log_id, excuse, excuse_type, confidence, reason, policy, "inconclusive")

                    elif time_eval["valid"]:
                        # 실제 일정 충돌 있음 -> 인정
                        st.info("📅 캘린더에 일정이 있었네요. 바쁜 하루였겠어요.")
                        st.success("🕐 다른 시간대에 운동을 해볼까요? 또는 내일을 기대해요!")
                        db.add_excuse_log(log_id, excuse, excuse_type, confidence, reason, policy, time_eval.get("reason"))

                    else:
                        # 일정 충돌 없음 -> 거짓 핑계
                        st.error("❌ 운동 시간에 캘린더 일정이 없습니다.\n\n시간이 충분하셨을 것 같아요.")
                        st.success("👉 이 핑계는 일정으로는 정당화되기 어려워요.\n\n운동하러 가볼까요?")
                        db.add_excuse_log(log_id, excuse, excuse_type, confidence, reason, policy, "claimed_time_but_no_conflict")

                elif policy == "LOW_INTENSITY":
                    st.info("😮‍💨 컨디션이 낮은 날이에요. 5분만 움직여도 충분해요.")
                    db.add_excuse_log(log_id, excuse, excuse_type, confidence, reason, policy, "low_intensity")

                elif policy == "SAFE_SKIP":
                    st.warning("🩺 건강 문제는 최우선이에요. 오늘은 쉬세요.")
                    db.add_excuse_log(log_id, excuse, excuse_type, confidence, reason, policy, "safe_skip")

                else:
                    st.info("오늘을 돌아보고 내일을 준비해볼까요?")
                    db.add_excuse_log(log_id, excuse, excuse_type, confidence, reason, policy, "neutral")

    else:
        if st.session_state.last_check_date == today:
            st.info("✅ 오늘 운동 여부는 이미 기록했어요.")
        else:
            st.info("⏳ 아직 운동 시간이 아니에요.")
