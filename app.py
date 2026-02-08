import streamlit as st
from datetime import datetime, date
from dotenv import load_dotenv

from llm_excuse_classifier import classify_excuse
from weather import get_weather

load_dotenv()

# =======================
# 정책 매핑 (🔥 energy 정합성 수정)
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
# 날씨 요약 함수
# =======================
def get_weather_summary(city="Seoul"):
    """
    실제 날씨 사실 기반 판단
    (사용자 발화와 분리)
    """
    data = get_weather(city)

    weather_main = data["weather"][0]["main"].lower()
    weather_desc = data["weather"][0]["description"]
    temp = data["main"]["temp"]

    bad_weather_keywords = ["rain", "snow", "thunderstorm"]
    is_bad_weather = any(k in weather_main for k in bad_weather_keywords)

    if temp <= 0:
        is_bad_weather = True
        reason = "기온이 매우 낮아 야외 운동이 부담스러워요."
    elif is_bad_weather:
        reason = "비나 눈 등으로 야외 운동이 어려워요."
    else:
        reason = "날씨는 운동을 방해할 정도는 아니에요."

    return {
        "condition": "bad" if is_bad_weather else "good",
        "weather": weather_desc,
        "temp": temp,
        "reason": reason,
        "suggestion": "실내 스트레칭" if is_bad_weather else "가벼운 야외 걷기"
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
    days = st.multiselect(
        "운동 요일",
        ["월", "화", "수", "목", "금", "토", "일"]
    )
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

    # -----------------------
    # 운동 요일 아님
    # -----------------------
    if not is_exercise_day:
        st.info(f"📌 오늘은 운동 요일이 아니에요 ({today_weekday}). 휴식일이에요.")

    # -----------------------
    # 운동 시간 지남 + 미체크
    # -----------------------
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

                # -----------------------
                # WEATHER_CHECK
                # -----------------------
                if policy == "WEATHER_CHECK":
                    try:
                        weather = get_weather_summary()

                        st.subheader("🌤️ 실제 날씨 분석")

                        # 🔹 사용자 인식 (LLM)
                        st.write("🧠 AI 인식:")
                        st.write("→ 날씨를 운동을 막는 주요 이유로 인식했어요.")

                        # 🔹 객관적 사실 (API)
                        st.write("🌍 실제 날씨:")
                        st.write(f"- 상태: {weather['weather']}")
                        st.write(f"- 기온: {weather['temp']}°C")
                        st.write(f"- 판단: {weather['reason']}")

                        st.divider()

                        if weather["condition"] == "bad":
                            st.success(
                                "오늘은 실제로도 날씨가 좋지 않아요.\n\n"
                                "👉 날씨 때문에 운동하기 어려웠다는 판단이 타당해 보여요."
                            )
                            st.info(f"🏠 추천: {weather['suggestion']}")
                        else:
                            st.warning(
                                "실제 날씨는 운동을 막을 정도는 아니에요."
                            )

                            if confidence < 0.6:
                                st.info(
                                    "🤔 핑계에 대한 확신도는 높지 않아요.\n\n"
                                    "5분만 가볍게 시작해보는 건 어떨까요?"
                                )
                            else:
                                st.info("💪 짧은 스트레칭이라도 해볼까요?")

                    except Exception as e:
                        st.error(f"⚠️ 날씨 정보를 불러오지 못했어요. {e}")

                # -----------------------
                # ENERGY
                # -----------------------
                elif policy == "LOW_INTENSITY":
                    st.info(
                        "😮‍💨 에너지가 낮은 날이에요.\n\n"
                        "5분 스트레칭이나 호흡 운동만 해도 충분해요."
                    )

                # -----------------------
                # HEALTH
                # -----------------------
                elif policy == "SAFE_SKIP":
                    st.warning(
                        "🩺 건강 문제는 최우선이에요.\n\n"
                        "오늘은 과감히 쉬는 것도 좋은 선택이에요."
                    )

                # -----------------------
                # 기타
                # -----------------------
                else:
                    st.info(
                        "오늘은 쉬었지만,\n\n"
                        "내일을 위해 컨디션을 정리해볼까요?"
                    )

    # -----------------------
    # 아직 시간 전 / 이미 체크
    # -----------------------
    else:
        if st.session_state.last_check_date == today:
            st.info("✅ 오늘 운동 여부는 이미 기록했어요.")
        else:
            st.info("⏳ 아직 운동 시간이 아니에요.")
