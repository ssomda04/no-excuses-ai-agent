import streamlit as st
import time
from llm_excuse_classifier import classify_excuse

st.title("No Excuses AI Agent")
st.write("데이터 기반 핑계 격파 운동 코치")

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
