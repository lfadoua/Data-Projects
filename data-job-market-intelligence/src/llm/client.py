"""Provider abstraction with bounded requests and validated structured output."""

from typing import Protocol

import httpx

from src.config.settings import get_settings


class LLMProvider(Protocol):
    def generate_text(self, instructions: str, content: str) -> tuple[str, dict]: ...
    def generate_structured(self, instructions: str, content: str, schema): ...


class OpenAIClient:
    def __init__(self):
        self.settings = get_settings()

    def request(self, instructions, content, schema=None):
        s = self.settings
        if not s.openai_api_key.get_secret_value() or not s.llm_model:
            raise ValueError("Set OPENAI_API_KEY and LLM_MODEL for generated answers")
        payload = {
            "model": s.llm_model,
            "instructions": instructions,
            "input": content,
            "max_output_tokens": 1600,
            "store": False,
        }
        if schema:
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "grounded_answer",
                    "strict": True,
                    "schema": schema.model_json_schema(),
                }
            }
        response = httpx.post(
            "https://api.openai.com/v1/responses",
            timeout=90,
            headers={"Authorization": "Bearer " + s.openai_api_key.get_secret_value()},
            json=payload,
        )
        response.raise_for_status()
        body = response.json()
        if body.get("status") not in (None, "completed"):
            raise ValueError("Model response was incomplete")
        output = "".join(
            c.get("text", "")
            for item in body.get("output", [])
            for c in item.get("content", [])
            if c.get("type") == "output_text"
        )
        if not output:
            raise ValueError("Model returned no answer or refused")
        return output, body.get("usage", {})

    def generate_text(self, instructions, content):
        return self.request(instructions, content)

    def generate_structured(self, instructions, content, schema):
        output, usage = self.request(instructions, content, schema)
        return schema.model_validate_json(output), usage


class OllamaClient:
    def generate_text(self, instructions, content):
        s = get_settings()
        if not s.llm_model:
            raise ValueError("Set LLM_MODEL to an installed Ollama model")
        response = httpx.post(
            s.ollama_url.rstrip("/") + "/api/generate",
            timeout=120,
            json={"model": s.llm_model, "system": instructions, "prompt": content, "stream": False},
        )
        response.raise_for_status()
        body = response.json()
        return body["response"], {
            "input_tokens": body.get("prompt_eval_count"),
            "output_tokens": body.get("eval_count"),
        }

    def generate_structured(self, instructions, content, schema):
        s = get_settings()
        if not s.llm_model:
            raise ValueError("Set LLM_MODEL to an installed Ollama model")
        response = httpx.post(
            s.ollama_url.rstrip("/") + "/api/generate",
            timeout=120,
            json={
                "model": s.llm_model,
                "system": instructions,
                "prompt": content,
                "format": schema.model_json_schema(),
                "stream": False,
                "options": {"temperature": 0},
            },
        )
        response.raise_for_status()
        body = response.json()
        return schema.model_validate_json(body["response"]), {
            "input_tokens": body.get("prompt_eval_count"),
            "output_tokens": body.get("eval_count"),
        }


def get_client():
    provider = get_settings().llm_provider
    if provider == "openai":
        return OpenAIClient()
    if provider == "ollama":
        return OllamaClient()
    raise ValueError("Extractive mode does not call a generative LLM")
