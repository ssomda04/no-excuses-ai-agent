import streamlit as st
import time
from datetime import datetime, date
from llm_excuse_classifier import classify_excuse
from weather import get_weather, analyze_weather
from dotenv import load_dotenv

load_dotenv()


# -----------------------
# 정책 매핑
# -----------------------
EXCUSE_POLICY = {
    "weather": "WEATHER_CHECK",
    "time": "TIME_CHECK",
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

# -----------------------
# session_state 초기화
# -----------------------
if "onboarded" not in st.session_state:
    st.session_state.onboarded = False

if "user" not in st.session_state:
    st.session_state.user = {}

if "last_check_date" not in st.session_state:
    st.session_state.last_check_date = None

# -----------------------
# UI
# -----------------------
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
        st.info(
            f"📌 오늘은 운동 요일이 아니에요 ({today_weekday}).\n\n"
            "오늘은 휴식일이에요."
        )

    # -----------------------
    # 운동 요일 + 시간 지남 + 아직 체크 안함
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
                st.subheader("AI 분석 결과")
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
                # 정책별 개입
                # -----------------------
                if policy == "WEATHER_CHECK":
                    try:
                        weather_data = get_weather()
                        weather_result = analyze_weather(weather_data)

                        st.info(
                            f"🌤️ 오늘 날씨 분석 결과: {weather_result['reason']}\n\n"
                            f"👉 추천: {weather_result['suggestion']}"
                        )

                        if weather_result["condition"] == "good":
                            st.success("💪 날씨는 문제 없어요. 짧게라도 시작해볼까요?")
                        else:
                            st.warning("🏠 오늘은 실내 운동이 더 좋아 보여요.")

                    except Exception as e:
                        st.error(f"⚠️ 날씨 정보를 불러오지 못했어요.{e}")

                elif policy == "TIME_CHECK":
                    st.info("⏰ 다른 시간대로 옮기는 건 어떠세요?")

                elif policy == "LOW_INTENSITY":
                    st.info("😮‍💨 컨디션이 낮은 날이에요. 5분 스트레칭도 충분해요.")

                elif policy == "SAFE_SKIP":
                    st.warning("🩺 오늘은 휴식이 더 중요해 보여요.")

                elif policy == "NEUTRAL_REFLECT":
                    st.info(
                        "오늘은 쉬었지만, 내일을 위해 컨디션을 정리해볼까요?"
                    )

    # -----------------------
    # 운동 요일이지만 아직 시간 전 or 이미 체크
    # -----------------------
    else:
        if st.session_state.last_check_date == today:
            st.info("✅ 오늘 운동 여부는 이미 기록했어요.")
        else:
            st.info("⏳ 아직 운동 시간이 아니에요.")
