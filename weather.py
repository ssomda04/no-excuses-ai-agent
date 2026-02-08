import requests
import os

API_KEY = os.getenv("OPENWEATHER_API_KEY")
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


def get_weather(city="Seoul"):
    params = {
        "q": city,
        "appid": API_KEY,
        "units": "metric",
        "lang": "kr"
    }

    response = requests.get(BASE_URL, params=params, timeout=5)
    response.raise_for_status()
    return response.json()


def analyze_weather(weather_data):
    """
    날씨 데이터를 Agent 판단용으로 단순화
    """
    main = weather_data["weather"][0]["main"]
    description = weather_data["weather"][0]["description"]
    temp = weather_data["main"]["temp"]

    # 핵심 판단
    if main in ["Rain", "Snow", "Thunderstorm"]:
        return {
            "condition": "bad",
            "reason": description,
            "suggestion": "실내 운동"
        }

    if temp >= 33:
        return {
            "condition": "bad",
            "reason": "폭염",
            "suggestion": "실내 운동"
        }

    if temp <= -5:
        return {
            "condition": "bad",
            "reason": "한파",
            "suggestion": "실내 스트레칭"
        }

    return {
        "condition": "good",
        "reason": "운동하기 무난한 날씨",
        "suggestion": "야외 운동 가능"
    }
