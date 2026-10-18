# backend/app/services/llm_client.py

import os

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

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
    預設使用 gemini-3.1-flash-lite（成本試算即以此模型計價）。
    """

    return os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")


def get_thinking_config(model_name: str) -> types.ThinkingConfig | None:
    """Gemini 3 系列的思考設定。

    Gemini 3 系列無法關閉思考，思考 token 依輸出單價計費；
    不指定時模型可能用較高的思考等級，實際費用會遠高於成本試算。
    因此預設用最低的 minimal，可用 GEMINI_THINKING_LEVEL 調整
    （minimal、low、medium、high）。2.5 系列沿用原本行為，不送出設定。
    """
    if not model_name.startswith("gemini-3"):
        return None

    level = os.getenv("GEMINI_THINKING_LEVEL", "minimal").strip().upper()
    return types.ThinkingConfig(thinking_level=getattr(types.ThinkingLevel, level, types.ThinkingLevel.MINIMAL))


def _is_thinking_config_rejected(error: errors.APIError) -> bool:
    """模型不支援指定的思考等級時，Gemini 回 400 並在訊息中提到 thinking。"""
    return error.code == 400 and "thinking" in str(error).lower()


# 產生式任務（問答、洞察）留一點變化比較自然；
# 分類任務要的是「最可能的那一個標籤」，temperature 越低越穩定。
DEFAULT_TEMPERATURE = 0.3
CLASSIFY_TEMPERATURE = 0.0


def generate_json_response(prompt: str, temperature: float = DEFAULT_TEMPERATURE) -> str:
    """
    把 prompt 送給 Gemini 並要求回傳 JSON。

    temperature 預設 0.3，適合要產生文字的用途。
    分類請傳 CLASSIFY_TEMPERATURE：實測同一組 prompt 在 0.3 下重跑，
    100 篇文章裡有 12 篇會得到不同標籤，使得「改了 prompt 有沒有變好」
    根本量不出來——雜訊比想驗證的差異還大。

    流程：
    1. 從 .env 取得 GOOGLE_API_KEY
    2. 設定 Gemini SDK
    3. 建立 model
    4. 送出 prompt
    5. 回傳 response.text 給後續 service 解析 JSON
    """

    client = get_gemini_client()
    model_name = get_gemini_model_name()
    thinking_config = get_thinking_config(model_name)

    def call(thinking):
        return client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=temperature,
                thinking_config=thinking,
            ),
        )

    try:
        try:
            response = call(thinking_config)
        except errors.APIError as error:
            # 模型不接受這個思考等級時，改用模型預設值重送一次，避免整個 AI 功能失效。
            if thinking_config is None or not _is_thinking_config_rejected(error):
                raise
            response = call(None)
    except errors.APIError as error:
        # 說明：
        # 429（rate limit / 額度用完）、402（預付額度用盡）和所有 5xx
        # 都屬於「現在無法使用 AI」的狀況，呼叫端應 fallback 或顯示
        # 「AI 暫時無法使用」，而不是回 500 讓整個頁面出錯。
        # 402 是 115/10/18 實際遇到：儲值用完後分析頁直接 500。
        # 其他錯誤（401 API key 錯誤、400 請求格式錯誤等）是設定問題，
        # 需要原樣拋出方便 debug。
        if error.code in (402, 429) or (error.code is not None and error.code >= 500):
            raise LLMServiceUnavailableError(
                "Gemini model is temporarily unavailable or overloaded."
            ) from error

        raise

    return response.text
