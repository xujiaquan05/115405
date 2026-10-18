# backend/tests/test_llm_client.py

import pytest
from google.genai import errors

from app.services import llm_client
from app.services.llm_client import LLMServiceUnavailableError, generate_json_response


class _FailingModels:
    def __init__(self, code):
        self.code = code

    def generate_content(self, **kwargs):
        raise errors.ClientError(self.code, {"error": {"code": self.code, "message": "x", "status": "X"}})


class _Client:
    def __init__(self, code):
        self.models = _FailingModels(code)


@pytest.mark.parametrize("code", [402, 429])
def test_quota_errors_become_service_unavailable(monkeypatch, code):
    """額度用完（402 預付儲值用盡、429 速率限制）要讓呼叫端走降級，不能變成 500。"""
    monkeypatch.setattr(llm_client, "get_gemini_client", lambda: _Client(code))

    with pytest.raises(LLMServiceUnavailableError):
        generate_json_response("prompt")


def test_configuration_errors_are_not_hidden(monkeypatch):
    """401 等設定錯誤照原樣拋出，方便除錯。"""
    monkeypatch.setattr(llm_client, "get_gemini_client", lambda: _Client(401))

    with pytest.raises(errors.ClientError):
        generate_json_response("prompt")
