import streamlit as st
from datetime import datetime, date
from dotenv import load_dotenv

from llm_excuse_classifier import classify_excuse
from weather import get_weather

load_dotenv()

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

    return {
        "rain": is_rain,
        "snow": is_snow,
        "temp": temp,
        "desc": weather_desc
    }


def evaluate_weather_excuse(user_excuse_text, weather_fact):
    """
    사용자 발화 vs 실제 날씨 불일치 판단
    """
    claimed_rain = "비" in user_excuse_text or "rain" in user_excuse_text.lower()

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
                        st.error(
                            "❌ 비가 온다고 했지만 실제로는 비가 오지 않았어요.\n\n"
                            "날씨가 운동을 막은 건 아니에요."
                        )
                        st.success(
                            "👉 이 핑계는 날씨로는 정당화되기 어려워요.\n\n"
                            "운동하러 가볼까요?"
                        )

                    # ✅ 합당한 날씨
                    else:
                        st.info(
                            "오늘은 날씨가 운동하기에 부담스러웠을 수 있어요."
                        )
                        st.success("🏠 추천: 실내 스트레칭 10분")

                elif policy == "LOW_INTENSITY":
                    st.info("😮‍💨 컨디션이 낮은 날이에요. 5분만 움직여도 충분해요.")

                elif policy == "SAFE_SKIP":
                    st.warning("🩺 건강 문제는 최우선이에요. 오늘은 쉬세요.")

                else:
                    st.info("오늘을 돌아보고 내일을 준비해볼까요?")

    else:
        if st.session_state.last_check_date == today:
            st.info("✅ 오늘 운동 여부는 이미 기록했어요.")
        else:
            st.info("⏳ 아직 운동 시간이 아니에요.")
