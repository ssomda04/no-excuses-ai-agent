from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.3
)

response = llm.invoke("너는 지금 정상적으로 동작하고 있니?")

print(response.content)
