import httpx
import pytest
from pydantic import SecretStr, ValidationError

from src.config.settings import Settings
from src.llm.client import OllamaClient, OpenAIClient
from src.llm.structured_output import GeneratedAnswer


def test_openai_structured_contract_without_paid_calls(monkeypatch):
    from src.llm import client

    monkeypatch.setattr(
        client,
        "get_settings",
        lambda: Settings(openai_api_key=SecretStr("test"), llm_model="configured-test-model"),
    )

    def fake_post(url, **kwargs):
        payload = kwargs["json"]
        assert payload["store"] is False
        assert payload["text"]["format"]["strict"] is True
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "status": "completed",
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"claims": [], "insufficient_evidence": true}',
                            }
                        ]
                    }
                ],
                "usage": {"input_tokens": 20, "output_tokens": 10},
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    answer, usage = OpenAIClient().generate_structured("instructions", "context", GeneratedAnswer)
    assert answer.insufficient_evidence
    assert usage["input_tokens"] == 20


@pytest.mark.parametrize("num_gpu", [None, 0])
def test_ollama_text_cpu_option_and_usage_without_network(monkeypatch, num_gpu):
    from src.llm import client

    monkeypatch.setattr(
        client,
        "get_settings",
        lambda: Settings(llm_model="configured-test-model", ollama_num_gpu=num_gpu),
    )

    def fake_post(url, **kwargs):
        assert url == "http://localhost:11434/api/generate"
        payload = kwargs["json"]
        assert payload["model"] == "configured-test-model"
        assert payload["system"] == "instructions"
        assert payload["prompt"] == "context"
        assert payload["stream"] is False
        if num_gpu is None:
            assert "options" not in payload
        else:
            assert payload["options"] == {"num_gpu": 0}
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"response": "Bonjour", "prompt_eval_count": 12, "eval_count": 3},
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    answer, usage = OllamaClient().generate_text("instructions", "context")
    assert answer == "Bonjour"
    assert usage == {"input_tokens": 12, "output_tokens": 3}


@pytest.mark.parametrize("num_gpu", [None, 0])
def test_ollama_structured_cpu_option_and_usage_without_network(monkeypatch, num_gpu):
    from src.llm import client

    monkeypatch.setattr(
        client,
        "get_settings",
        lambda: Settings(llm_model="configured-test-model", ollama_num_gpu=num_gpu),
    )

    def fake_post(url, **kwargs):
        assert url == "http://localhost:11434/api/generate"
        payload = kwargs["json"]
        assert payload["format"] == GeneratedAnswer.model_json_schema()
        assert payload["stream"] is False
        assert payload["options"]["temperature"] == 0
        if num_gpu is None:
            assert "num_gpu" not in payload["options"]
        else:
            assert payload["options"]["num_gpu"] == 0
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "response": (
                    '{"claims": [{"text": "Build pipelines", "source_id": "S1", '
                    '"quote": "Build Python data pipelines."}], "insufficient_evidence": false}'
                ),
                "prompt_eval_count": 45,
                "eval_count": 24,
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    answer, usage = OllamaClient().generate_structured("instructions", "context", GeneratedAnswer)
    assert answer.insufficient_evidence is False
    assert answer.claims[0].source_id == "S1"
    assert answer.claims[0].quote == "Build Python data pipelines."
    assert usage == {"input_tokens": 45, "output_tokens": 24}


def test_ollama_gpu_count_cannot_be_negative():
    with pytest.raises(ValidationError):
        Settings(ollama_num_gpu=-1)
