"""
캘린더 형식 통계 시각화
"""
import streamlit as st
import calendar as cal_module
from datetime import date, datetime, timedelta
import db


def render_calendar_view(user_id: int, user_name: str, plan_days: list):
    """
    월별 캘린더 형식으로 운동 기록과 핑계를 시각화
    plan_days: 운동 계획 요일 리스트 (예: ["월", "화", "수"])
    """
    st.subheader(f"📊 {user_name}님의 운동 기록")
    
    # 월 선택 (< > 네비게이션)
    col1, col2, col3, col4, col5 = st.columns([1, 1, 3, 1, 1])
    
    if "calendar_year" not in st.session_state:
        st.session_state.calendar_year = date.today().year
    if "calendar_month" not in st.session_state:
        st.session_state.calendar_month = date.today().month
    
    with col1:
        if st.button("◀ 이전"):
            st.session_state.calendar_month -= 1
            if st.session_state.calendar_month < 1:
                st.session_state.calendar_month = 12
                st.session_state.calendar_year -= 1
            st.rerun()
    
    with col3:
        st.markdown(
            f"<div style='text-align: center; font-size: 20px; font-weight: 600;'>"
            f"{st.session_state.calendar_year}년 {st.session_state.calendar_month}월"
            f"</div>",
            unsafe_allow_html=True
        )
    
    with col5:
        if st.button("다음 ▶"):
            st.session_state.calendar_month += 1
            if st.session_state.calendar_month > 12:
                st.session_state.calendar_month = 1
                st.session_state.calendar_year += 1
            st.rerun()
    
    selected_year = st.session_state.calendar_year
    selected_month = st.session_state.calendar_month
    
    # DB에서 데이터 조회
    exercise_logs = db.get_exercise_logs_by_month(user_id, selected_year, selected_month)
    excuse_summary = db.get_excuse_summary_by_month(user_id, selected_year, selected_month)
    
    # 데이터 변환
    exercise_dict = {log[0]: log[1] for log in exercise_logs}  # {date_str: did_exercise}
    
    # 요일 명칭 매핑 (0=월, 1=화, ..., 6=일)
    WEEKDAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]
    
    st.divider()
    
    # 캘린더 헤더
    col_headers = st.columns(7)
    for i, name in enumerate(WEEKDAY_NAMES):
        with col_headers[i]:
            st.markdown(
                f"<div style='text-align: center; font-weight: 600;'>{name}</div>",
                unsafe_allow_html=True
            )
    
    st.divider()
    
    # 달력 생성
    cal = cal_module.monthcalendar(selected_year, selected_month)
    
    for week in cal:
        cols = st.columns(7)
        for day_idx, day in enumerate(week):
            with cols[day_idx]:
                if day == 0:
                    st.write("")  # 다른 달의 날짜
                else:
                    date_str = f"{selected_year:04d}-{selected_month:02d}-{day:02d}"
                    weekday_name = WEEKDAY_NAMES[day_idx]
                    is_plan_day = weekday_name in plan_days
                    
                    # 데이터 조회
                    did_exercise = exercise_dict.get(date_str)
                    
                    # 계획 요일 여부에 따라 표시 결정
                    if is_plan_day:
                        # 계획 요일: 운동 여부 표시
                        if did_exercise is None:
                            # 기록 없음 (계획 요일 강조)
                            st.markdown(f"""
                            <div style='border: 1px solid #e0e0e0; background-color: #f1f8e9; padding: 6px; border-radius: 6px; text-align: center; min-height: 60px;'>
                                <div style='font-size: 12px; color: #666;'>{day}</div>
                                <div style='font-size: 24px; margin-top: 4px;'>•</div>
                            </div>
                            """, unsafe_allow_html=True)
                        elif did_exercise == 1:
                            # 운동 완료
                            st.markdown(f"""
                            <div style='background-color: #c8e6c9; border: 1px solid #c8e6c9; padding: 6px; border-radius: 6px; text-align: center; min-height: 60px;'>
                                <div style='font-size: 12px; color: #2e7d32;'>{day}</div>
                                <div style='font-size: 24px; margin-top: 4px;'>✅</div>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            # 핑계 댐
                            st.markdown(f"""
                            <div style='background-color: #ffcdd2; border: 1px solid #ffcdd2; padding: 6px; border-radius: 6px; text-align: center; min-height: 60px;'>
                                <div style='font-size: 12px; color: #c62828;'>{day}</div>
                                <div style='font-size: 24px; margin-top: 4px;'>❌</div>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        # 비계획 요일: 운동하면 보너스(✅), 아니면 표시 안 함
                        if did_exercise == 1:
                            st.markdown(f"""
                            <div style='background-color: #b3e5fc; border: 1px solid #b3e5fc; padding: 6px; border-radius: 6px; text-align: center; min-height: 60px;'>
                                <div style='font-size: 12px; color: #0277bd;'>{day}</div>
                                <div style='font-size: 24px; margin-top: 4px;'>🎁</div>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            # 기록 없음 (비계획 요일은 날짜만 표시)
                            st.markdown(f"""
                            <div style='border: 1px solid #e0e0e0; padding: 6px; border-radius: 6px; text-align: center; min-height: 60px;'>
                                <div style='font-size: 12px; color: #666;'>{day}</div>
                                <div style='font-size: 24px; margin-top: 4px;'>&nbsp;</div>
                            </div>
                            """, unsafe_allow_html=True)
    
    st.divider()
    
    # 통계 요약
    st.subheader("📈 월별 통계")
    total_days = len(exercise_logs)
    completed_days = sum(1 for log in exercise_logs if log[1] == 1)
    excuse_days = sum(1 for log in exercise_logs if log[1] == 0)

    # 목표 운동 일자(계획 요일) 대비 성공률 계산
    planned_days = 0
    planned_completed = 0
    for week in cal:
        for day_idx, day in enumerate(week):
            if day == 0:
                continue
            weekday_name = WEEKDAY_NAMES[day_idx]
            if weekday_name not in plan_days:
                continue
            planned_days += 1
            date_str = f"{selected_year:04d}-{selected_month:02d}-{day:02d}"
            if exercise_dict.get(date_str) == 1:
                planned_completed += 1
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("✅ 운동 완료", completed_days)
    with col2:
        st.metric("❌ 핑계", excuse_days)
    with col3:
        if planned_days > 0:
            success_rate = (planned_completed / planned_days) * 100
            st.metric("성공률", f"{success_rate:.1f}%")
        else:
            st.metric("성공률", "N/A")
    
    st.divider()
    
    # 핑계 유형 분포
    if excuse_summary:
        st.subheader("🎯 핑계 유형 분포")
        excuse_counts = {}
        for excuses in excuse_summary.values():
            for exc in excuses:
                excuse_counts[exc] = excuse_counts.get(exc, 0) + 1
        
        for exc_type, count in sorted(excuse_counts.items(), key=lambda x: x[1], reverse=True):
            st.write(f"- {exc_type}: {count}회")

