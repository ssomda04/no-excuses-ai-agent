from dotenv import load_dotenv
load_dotenv()

from typing import Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser


# =======================
# 1️⃣ 출력 스키마 정의
# =======================
class ExcuseAnalysis(BaseModel):
    excuse_type: Literal[
        "weather", "time", "fatigue", "emotion", "health", "other"
    ] = Field(description="핑계의 주된 원인 분류")

    weather_reason: Literal[
        "rain", "snow", "cold", "heat", "wind", "dust", "unknown"
    ] = Field(description="날씨 관련 세부 사유, 날씨 핑계가 아닐 경우 unknown")

    confidence: float = Field(
        ge=0.0, le=1.0, description="분류에 대한 모델의 확신도"
    )

    reason: str = Field(description="판단 근거 요약")


# =======================
# 2️⃣ Parser / LLM
# =======================
parser = PydanticOutputParser(pydantic_object=ExcuseAnalysis)

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0
)


# =======================
# 3️⃣ Prompt
# =======================
prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
너는 사용자의 '운동을 못 한 이유'를 의미적으로 분석하는 AI 코치다.

- 단어가 아니라 '의미' 기준으로 판단하라.
- 같은 뜻의 다른 표현도 정확히 분류하라.
- 날씨 핑계라면 어떤 날씨 요인인지 추론하라.

{format_instructions}
"""
    ),
    ("human", "{excuse}")]).partial(
    format_instructions=parser.get_format_instructions()
)


# =======================
# 4️⃣ Chain
# =======================
chain = prompt | llm | parser


# =======================
# 5️⃣ 외부 인터페이스
# =======================
def classify_excuse(excuse: str) -> dict:
    """
    app.py에서 사용하는 핑계 분석 함수
    """
    result: ExcuseAnalysis = chain.invoke({"excuse": excuse})
    return result.model_dump()
