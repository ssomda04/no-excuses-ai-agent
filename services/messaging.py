from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)


def generate_escalation_message(user_name: str, excuse_type: str, count: int, window_days: int) -> str:
    """
    간단한 문맥(사용자 이름, 핑계 유형, 발생 횟수, 기간)을 받아 설득력 있는 한국어 메시지를 생성합니다.
    """
    prompt = (
        f"{user_name}님, 지난 {window_days}일 동안 '" + excuse_type + "' 유형의 핑계가 {count}회 감지되었습니다. "
        "친절하면서도 단호하게 운동을 권하는 한두 문장으로 응답해주세요. 상황을 공감하되, 동기를 부여하는 톤으로 작성하세요. "
        "한국어로 1-2문장으로 출력하세요."
    )

    resp = llm.invoke(prompt)
    # langchain_openai ChatOpenAI may return an object; try to extract text
    try:
        return resp[0].text if isinstance(resp, list) else str(resp)
    except Exception:
        return str(resp)
