import streamlit as st

st.title("No Excuses AI Agent")
st.write("데이터 기반 핑계 격파 운동 코치")

excuse = st.text_input("오늘 운동 못 하는 이유를 말해보세요")

if excuse:
    st.subheader("AI 분석 결과")

    if "비" in excuse:
        st.write("📊 오늘 강수 확률: 20%")
        st.write("❌ 비 핑계는 성립하지 않습니다.")
        st.success("👉 야외 운동 가능합니다.")

    elif "피곤" in excuse:
        st.write("📊 어제 수면 시간: 7.2시간")
        st.write("❌ 피곤하다는 주장은 근거가 부족합니다.")
        st.success("👉 가벼운 운동 추천")

    else:
        st.write("🤔 새로운 핑계군요.")
        st.success("👉 그래도 운동은 가능합니다.")
