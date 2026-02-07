from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0
)

parser = JsonOutputParser()

prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
너는 사용자의 '운동 핑계'를 분석하는 AI 코치다.

사용자의 발화를 보고 아래 JSON 형식으로만 응답하라.

{{
  "excuse_type": "weather | time | energy | emotion | health | other ",
  "validity": true | false,
  "confidence": 0.0 ~ 1.0,
  "reason": "판단 근거 요약"
}}
"""
    ),
    ("human", "{excuse}")
])


chain = prompt | llm | parser


def classify_excuse(excuse: str):
    return chain.invoke({"excuse": excuse})
