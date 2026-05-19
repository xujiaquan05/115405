# backend/app/services/llm_client.py

import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Note:
# Load biến môi trường từ file .env.
# Trong đó có GOOGLE_API_KEY và GEMINI_MODEL.
load_dotenv()


def get_gemini_client():
    """
    Note:
    Hàm này tạo Gemini client.

    Vì sao tách riêng?
    - Nếu sau này đổi API Key hoặc đổi model, chỉ cần sửa ở đây.
    - Các service khác không cần biết chi tiết cách kết nối Gemini.
    """

    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("Missing GOOGLE_API_KEY in .env file")

    return genai.Client(api_key=api_key)


def get_gemini_model_name() -> str:
    """
    Note:
    Lấy tên model từ .env.

    Nếu .env không có GEMINI_MODEL,
    mặc định dùng gemini-2.5-flash.
    """

    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def generate_json_response(prompt: str) -> str:
    """
    Note:
    Hàm này gửi prompt đến Gemini và yêu cầu model trả về JSON.

    Quy trình:
    1. Lấy GOOGLE_API_KEY từ .env
    2. Cấu hình Gemini SDK
    3. Tạo model
    4. Gửi prompt
    5. Trả về response.text cho service phía sau parse JSON
    """

    client = get_gemini_client()
    model_name = get_gemini_model_name()

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )

    return response.text