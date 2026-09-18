from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import Config  # noqa: E402
from utils import LLMService  # noqa: E402
from pydantic import BaseModel  # noqa: E402


def test_config_accepts_novaapi_provider(monkeypatch):
    monkeypatch.setenv("FOAMAGENT_MODEL_PROVIDER", "novaapi")
    monkeypatch.setenv("FOAMAGENT_MODEL_VERSION", "gpt-5.5")
    config = Config()
    assert config.model_provider == "novaapi"
    assert config.model_version == "gpt-5.5"


def test_llm_service_constructs_novaapi_provider_without_calling_network(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-key")
    monkeypatch.setenv("FOAMAGENT_MODEL_PROVIDER", "novaapi")
    monkeypatch.setenv("FOAMAGENT_MODEL_VERSION", "gpt-5.5")
    service = LLMService(Config())
    assert service.model_provider == "novaapi"
    assert service.model_version == "gpt-5.5"


def test_novaapi_refuses_openai_codex_default_model(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-key")
    monkeypatch.setenv("FOAMAGENT_MODEL_PROVIDER", "novaapi")
    monkeypatch.delenv("FOAMAGENT_MODEL_VERSION", raising=False)
    monkeypatch.delenv("CODEBUDDY_MODEL", raising=False)

    try:
        LLMService(Config())
    except ValueError as exc:
        assert "FOAMAGENT_MODEL_VERSION is required" in str(exc)
        assert "gpt-5.3-codex" in str(exc)
    else:
        raise AssertionError("novaapi must not silently use the openai-codex default model")


def test_config_accepts_codebuddy_provider(monkeypatch):
    monkeypatch.setenv("FOAMAGENT_MODEL_PROVIDER", "codebuddy")
    monkeypatch.setenv("CODEBUDDY_MODEL", "deepseek-v4-pro")
    config = Config()
    assert config.model_provider == "codebuddy"


def test_llm_service_constructs_codebuddy_provider_without_calling_network(monkeypatch):
    monkeypatch.setenv("FOAMAGENT_MODEL_PROVIDER", "codebuddy")
    monkeypatch.setenv("CODEBUDDY_API_KEY", "test-key")
    monkeypatch.setenv("CODEBUDDY_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("CODEBUDDY_MODEL", "deepseek-v4-pro")
    monkeypatch.delenv("FOAMAGENT_MODEL_VERSION", raising=False)
    service = LLMService(Config())
    assert service.model_provider == "codebuddy"
    assert service.model_version == "deepseek-v4-pro"


class _DummyStructuredModel(BaseModel):
    value: str


class _DummyResponse:
    content = '{"value": "ok"}'


class _DummyLLM:
    structured_called = False

    def get_num_tokens(self, text):
        return len(str(text))

    def with_structured_output(self, pydantic_obj):
        self.structured_called = True
        raise AssertionError("with_structured_output should not be used for deepseek models")

    def invoke(self, messages):
        return _DummyResponse()


def test_novaapi_deepseek_model_uses_json_prompt_structured_fallback():
    service = LLMService.__new__(LLMService)
    service.model_provider = "novaapi"
    service.model_version = "deepseek-v4-pro"
    service.temperature = 0
    service.llm = _DummyLLM()
    service.total_calls = 0
    service.total_prompt_tokens = 0
    service.total_completion_tokens = 0
    service.total_tokens = 0
    service.failed_calls = 0
    service.retry_count = 0

    response = service.invoke("hello", pydantic_obj=_DummyStructuredModel)

    assert response == _DummyStructuredModel(value="ok")
    assert service.llm.structured_called is False


def test_model_not_found_is_not_treated_as_retryable_throttling():
    service = LLMService.__new__(LLMService)
    error = Exception(
        "Error code: 503 - {'error': {'code': 'model_not_found', "
        "'message': '模型无可用渠道'}}"
    )

    assert service._is_throttling_error(error) is False
