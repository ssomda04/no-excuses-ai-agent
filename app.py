import streamlit as st
import time
from datetime import datetime, date
from llm_excuse_classifier import classify_excuse

# -----------------------
# 상수 / 정책 매핑
# -----------------------
EXCUSE_POLICY = {
    "weather": "WEATHER_CHECK",
    "time": "TIME_CHECK",
    "energy": "LOW_INTENSITY",
    "emotion": "MOTIVATION_PUSH",
    "health": "SAFE_SKIP",
    "other": "DEFAULT_PUSH"
}

# -----------------------
# session_state 초기화
# -----------------------
if "onboarded" not in st.session_state:
    st.session_state.onboarded = False

if "user" not in st.session_state:
    st.session_state.user = {}

# 오늘 운동 여부를 이미 물어봤는지 기록
if "last_check_date" not in st.session_state:
    st.session_state.last_check_date = None

# -----------------------
# UI 시작
# -----------------------
st.title("No Excuses AI Agent")
st.write("데이터 기반 핑계 격파 운동 코치")

# -----------------------
# 1️⃣ 온보딩
# -----------------------
if not st.session_state.onboarded:
    st.subheader("👤 사용자 정보 입력")

    name = st.text_input("이름 (필수)")
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

# -----------------------
# 2️⃣ 메인 로직
# -----------------------
else:
    user = st.session_state.user
    plan = user["plan"]

    st.subheader(f"💪 {user['name']}님의 운동 플랜")
    st.write(f"""
    - 📅 요일: {', '.join(plan['days'])}
    - ⏰ 시간: {plan['time']}
    """)

    st.divider()

    # -----------------------
    # 현재 시각 계산
    # -----------------------
    now = datetime.now()
    today = date.today()

    exercise_time_today = datetime.strptime(
        f"{today} {plan['time']}",
        "%Y-%m-%d %H:%M"
    )

    # -----------------------
    # 3️⃣ 운동 시간이 지났고, 아직 체크 안 했다면
    # -----------------------
    if now >= exercise_time_today and st.session_state.last_check_date != today:
        st.warning("⏰ 오늘 운동 시간이에요!")

        did_exercise = st.radio(
            "오늘 운동 하셨나요?",
            ["선택", "했어요", "못 했어요"]
        )

        if did_exercise == "했어요":
            st.success("🔥 최고예요! 오늘 운동 완료로 기록할게요.")
            st.session_state.last_check_date = today

        elif did_exercise == "못 했어요":
            st.session_state.last_check_date = today

            st.subheader("❓ 왜 못 하셨나요?")
            excuse = st.text_input("이유를 입력해주세요")

            if excuse:
                st.subheader("AI 분석 결과")

                result = classify_excuse(excuse)
                excuse_type = result["excuse_type"]
                policy = EXCUSE_POLICY.get(excuse_type, "DEFAULT_PUSH")

                st.write("🤖 적용된 Agent 정책:", policy)
                st.write("📌 핑계 유형:", excuse_type)
                st.write("🧠 판단 근거:", result["reason"])
                st.write("🔍 확신도:", round(result["confidence"], 2))

                # -----------------------
                # 4️⃣ 정책 기반 개입
                # -----------------------
                if policy == "WEATHER_CHECK":
                    st.info("🌦️ 날씨 확인 결과 → 실내 운동 제안")

                elif policy == "TIME_CHECK":
                    st.info("⏰ 일정 분석 → 다른 시간대 추천")

                elif policy == "LOW_INTENSITY":
                    st.info("😮‍💨 컨디션 고려 → 가벼운 운동 추천")

                elif policy == "SAFE_SKIP":
                    st.warning("🩺 건강 사유 인정 → 오늘은 휴식")

                else:
                    st.success("💥 핑계 반박 — 운동 가능")

                    if st.button("🏃 지금 운동 시작하기"):
                        with st.spinner("운동 중..."):
                            time.sleep(3)
                        st.success("🎉 운동 완료! 잘했어요.")

    else:
        st.info("📌 아직 운동 시간이 아니거나, 오늘은 이미 체크했어요.")
