import streamlit as st
import time
from llm_excuse_classifier import classify_excuse


st.write("DEBUG session_state")
st.write(st.session_state)

# -----------------------
# 1. session_state 초기화
# -----------------------
if "onboarded" not in st.session_state:
    st.session_state.onboarded = False

if "user" not in st.session_state:
    st.session_state.user = {}


st.title("No Excuses AI Agent")
st.write("데이터 기반 핑계 격파 운동 코치")

if not st.session_state.onboarded:
    st.subheader("👤 사용자 정보 입력")

    name = st.text_input("이름 (필수)")
    days = st.multiselect(
        "운동 요일",
        ["월", "화", "수", "목", "금", "토", "일"]
    )
    time = st.time_input("운동 시간")
    workout_type = st.selectbox(
        "운동 종류",
        ["러닝", "헬스", "홈트", "기타"]
    )

    if st.button("저장하고 시작하기"):
        if not name or not days:
            st.warning("이름과 운동 요일은 필수입니다.")
        else:
            st.session_state.user = {
                "name": name,
                "plan": {
                    "days": days,
                    "time": time.strftime("%H:%M"),
                    "type": workout_type
                }
            }
            st.session_state.onboarded = True
            st.rerun()
else:
    user = st.session_state.user

    st.subheader(f"💪 {user['name']}님의 운동 플랜")

    plan = user["plan"]
    st.write(f"""
    - 📅 요일: {', '.join(plan['days'])}
    - ⏰ 시간: {plan['time']}
    - 🏃 운동: {plan['type']}
    """)

    st.divider()

    st.write("👉 운동 시간이 되면 AI가 개입합니다 (다음 단계)")


excuse = st.text_input("오늘 운동 못 하는 이유를 말해보세요")

if excuse:
    st.subheader("AI 분석 결과")

    result = classify_excuse(excuse)

    # LLM 결과 표시
    st.write("📌 핑계 유형:", result["excuse_type"])
    st.write("🧠 판단 근거:", result["reason"])
    st.write("🔍 확신도:", round(result["confidence"], 2))

    # 판단 결과에 따른 분기
    if not result["validity"]:
        st.success("❌ 핑계 기각 — 운동 가능합니다.")

        if st.button("🏃 지금 운동 시작하기"):
            st.subheader("운동 시작!")
            with st.spinner("운동 중..."):
                time.sleep(3)
            st.success("🎉 운동 완료! 잘했어요.")

    else:
        st.warning("⚠️ 합리적인 핑계로 판단됨 — 대안 운동 제안 예정")
