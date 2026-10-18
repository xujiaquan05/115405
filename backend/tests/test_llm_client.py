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


class _RecordingModels:
    """記錄送出的設定；reject_thinking=True 時模擬模型不接受思考等級。"""

    def __init__(self, reject_thinking=False):
        self.configs = []
        self.reject_thinking = reject_thinking

    def generate_content(self, **kwargs):
        config = kwargs["config"]
        self.configs.append(config)
        if self.reject_thinking and config.thinking_config is not None:
            raise errors.ClientError(400, {"error": {"code": 400, "message": "thinking_level is not supported",
                                                     "status": "INVALID_ARGUMENT"}})

        class _Response:
            text = "{}"

        return _Response()


def _use_models(monkeypatch, models, model_name):
    client = type("C", (), {"models": models})()
    monkeypatch.setattr(llm_client, "get_gemini_client", lambda: client)
    monkeypatch.setenv("GEMINI_MODEL", model_name)
    monkeypatch.delenv("GEMINI_THINKING_LEVEL", raising=False)


def test_gemini3_uses_minimal_thinking(monkeypatch):
    """Gemini 3 系列的思考 token 依輸出計價，預設要壓到 minimal 才符合成本試算。"""
    models = _RecordingModels()
    _use_models(monkeypatch, models, "gemini-3.1-flash-lite")

    generate_json_response("prompt")

    assert models.configs[0].thinking_config.thinking_level == "MINIMAL"


def test_thinking_level_can_be_configured(monkeypatch):
    models = _RecordingModels()
    _use_models(monkeypatch, models, "gemini-3.1-flash-lite")
    monkeypatch.setenv("GEMINI_THINKING_LEVEL", "low")

    generate_json_response("prompt")

    assert models.configs[0].thinking_config.thinking_level == "LOW"


def test_gemini25_sends_no_thinking_config(monkeypatch):
    models = _RecordingModels()
    _use_models(monkeypatch, models, "gemini-2.5-flash-lite")

    generate_json_response("prompt")

    assert models.configs[0].thinking_config is None


def test_rejected_thinking_level_falls_back_to_model_default(monkeypatch):
    """模型不接受思考等級時改用預設值重送，AI 功能不能因此整個失效。"""
    models = _RecordingModels(reject_thinking=True)
    _use_models(monkeypatch, models, "gemini-3.1-flash-lite")

    assert generate_json_response("prompt") == "{}"
    assert [c.thinking_config is None for c in models.configs] == [False, True]
