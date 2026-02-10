from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)


def generate_coaching_advice(excuse_type: str, count: int, window_days: int) -> str:
    """
    운동 코치 톤의 권유/조언 부분만 생성합니다.
    (프리앰블은 app.py에서 조합)
    """
    prompt = (
        f"사용자가 지난 {window_days}일 동안 '{excuse_type}' 핑계를 {count}회 제시했습니다. "
        "운동 코치처럼 단호하고 직설적으로, 명확한 실행 권유를 한두 문장으로 작성하세요. "
        "반드시 존댓말을 사용하고, 상황을 약간 공감하되 명령에 가까운 톤으로. "
        "한국어만 사용, 1-2문장."
    )

    resp = llm.invoke(prompt)
    if hasattr(resp, 'content'):
        return resp.content
    return str(resp)


