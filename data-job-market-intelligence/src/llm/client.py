"""Provider abstraction with bounded requests and validated structured output."""

from typing import Protocol

import httpx

from src.config.settings import get_settings


class LLMProvider(Protocol):
    def generate_text(self, instructions: str, content: str) -> tuple[str, dict]: ...
    def generate_structured(self, instructions: str, content: str, schema): ...


class GenerationOutputError(ValueError):
    """A safe generation failure retaining measured usage, never provider content."""

    def __init__(self, message, usage):
        super().__init__(message)
        self.usage = usage


def ollama_usage(body):
    usage = {
        "input_tokens": body.get("prompt_eval_count"),
        "output_tokens": body.get("eval_count"),
    }
    durations = {}
    for source, target in (
        ("total_duration", "total"),
        ("load_duration", "load"),
        ("prompt_eval_duration", "prompt_evaluation"),
        ("eval_duration", "generation"),
    ):
        value = body.get(source)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
            durations[target] = value / 1_000_000
    if durations:
        usage["ollama_timings_ms"] = durations
    if body.get("done_reason") in ("stop", "length", "load", "unload"):
        usage["done_reason"] = body["done_reason"]
    return usage


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
        payload = {
            "model": s.llm_model,
            "system": instructions,
            "prompt": content,
            "stream": False,
        }
        if s.ollama_num_gpu is not None:
            payload["options"] = {"num_gpu": s.ollama_num_gpu}
        if s.ollama_num_predict is not None:
            payload.setdefault("options", {})["num_predict"] = s.ollama_num_predict
        response = httpx.post(
            s.ollama_url.rstrip("/") + "/api/generate",
            timeout=s.ollama_timeout_seconds,
            json=payload,
        )
        response.raise_for_status()
        body = response.json()
        usage = ollama_usage(body)
        if body.get("done") is False or body.get("done_reason") == "length":
            raise GenerationOutputError("Ollama output did not complete", usage)
        return body["response"], usage

    def generate_structured(self, instructions, content, schema):
        s = get_settings()
        if not s.llm_model:
            raise ValueError("Set LLM_MODEL to an installed Ollama model")
        payload = {
            "model": s.llm_model,
            "system": instructions,
            "prompt": content,
            "format": schema.model_json_schema(),
            "stream": False,
            "options": {"temperature": 0},
        }
        if s.ollama_num_gpu is not None:
            payload["options"]["num_gpu"] = s.ollama_num_gpu
        if s.ollama_num_predict is not None:
            payload["options"]["num_predict"] = s.ollama_num_predict
        response = httpx.post(
            s.ollama_url.rstrip("/") + "/api/generate",
            timeout=s.ollama_timeout_seconds,
            json=payload,
        )
        response.raise_for_status()
        body = response.json()
        usage = ollama_usage(body)
        if body.get("done") is False or body.get("done_reason") == "length":
            raise GenerationOutputError("Ollama output did not complete", usage)
        try:
            parsed = schema.model_validate_json(body["response"])
        except (ValueError, KeyError, TypeError):
            raise GenerationOutputError("Ollama output did not match the schema", usage) from None
        return parsed, usage


def get_client():
    provider = get_settings().llm_provider
    if provider == "openai":
        return OpenAIClient()
    if provider == "ollama":
        return OllamaClient()
    raise ValueError("Extractive mode does not call a generative LLM")
