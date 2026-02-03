import streamlit as st

st.title("No Excuses AI Agent")
st.write("데이터 기반 핑계 격파 운동 코치")

excuse = st.text_input("오늘 운동 못 하는 이유를 말해보세요")

if excuse:
    st.write(f"당신의 핑계: {excuse}")
