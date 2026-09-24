import httpx
from pydantic import SecretStr

from src.config.settings import Settings
from src.llm.client import OpenAIClient
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
