# backend/app/services/llm_client.py

import os
from dotenv import load_dotenv
from google import genai
from google.genai import errors
from google.genai import types

# 載入 .env 的環境變數，
# 其中包含 GOOGLE_API_KEY 和 GEMINI_MODEL。
load_dotenv()


class LLMServiceUnavailableError(Exception):
    """Gemini 暫時無法使用或過載時拋出。"""


def get_gemini_client():
    """
    建立 Gemini client。

    為什麼獨立成一個函式？
    - 之後更換 API Key 或 model 時只需要改這裡。
    - 其他 service 不需要知道連線 Gemini 的細節。
    """

    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("Missing GOOGLE_API_KEY in .env file")

    return genai.Client(api_key=api_key)


def get_gemini_model_name() -> str:
    """
    從 .env 讀取 model 名稱。

    如果 .env 沒有設定 GEMINI_MODEL，
    預設使用 gemini-2.5-flash。
    """

    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def generate_json_response(prompt: str) -> str:
    """
    把 prompt 送給 Gemini 並要求回傳 JSON。

    流程：
    1. 從 .env 取得 GOOGLE_API_KEY
    2. 設定 Gemini SDK
    3. 建立 model
    4. 送出 prompt
    5. 回傳 response.text 給後續 service 解析 JSON
    """

    client = get_gemini_client()
    model_name = get_gemini_model_name()

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
            ),
        )
    except errors.APIError as error:
        # 說明：
        # 429（rate limit / 額度用完）和所有 5xx 都屬於暫時性錯誤，
        # 呼叫端應 fallback 或顯示「AI 忙碌中」，而不是回 500。
        # 其他錯誤（401 API key 錯誤、400 請求格式錯誤等）是設定問題，
        # 需要原樣拋出方便 debug。
        if error.code == 429 or (error.code is not None and error.code >= 500):
            raise LLMServiceUnavailableError(
                "Gemini model is temporarily unavailable or overloaded."
            ) from error

        raise

    return response.text
