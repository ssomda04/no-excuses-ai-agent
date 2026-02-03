import streamlit as st
import time

def analyze_excuse(excuse: str):
    """
    사용자 핑계를 분석하고
    (evidence, message, can_exercise)를 반환
    """
    if "비" in excuse:
        evidence = "📊 오늘 강수 확률: 20%"
        message = "❌ 비 핑계는 성립하지 않습니다. 👉 야외 운동 가능합니다."
        return evidence, message, True

    elif "피곤" in excuse:
        evidence = "📊 어제 수면 시간: 7.2시간"
        message = "❌ 피곤하다는 주장은 근거가 부족합니다. 👉 가벼운 운동 추천"
        return evidence, message, True

    else:
        evidence = "📊 특이 사항 없음"
        message = "🤔 새로운 핑계지만, 운동은 가능합니다."
        return evidence, message, True


st.title("No Excuses AI Agent")
st.write("데이터 기반 핑계 격파 운동 코치")

excuse = st.text_input("오늘 운동 못 하는 이유를 말해보세요")

if excuse:
    st.subheader("AI 분석 결과")

    evidence, message, can_exercise = analyze_excuse(excuse)

    st.write(evidence)
    st.success(message)

    if can_exercise:
        if st.button("🏃 지금 운동 시작하기"):
            st.subheader("운동 시작!")
            with st.spinner("운동 중..."):
                time.sleep(3)
            st.success("🎉 운동 완료! 잘했어요.")
