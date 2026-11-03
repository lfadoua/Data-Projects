"""Offline response-mode API regressions using SQLite and mocked generation."""

import json
import math
import re
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.analytics.schemas import QueryRequest
from src.config.settings import get_settings
from src.llm.structured_output import GeneratedAnswer
from src.rag import service

ENDPOINTS = ("/api/assistant/query", "/api/rag/query")
QUESTION = "Describe Python data pipelines"
FILTERS = {"country": "France", "job_title": "Data Engineer"}
ANSWER_FIELDS = {
    "route",
    "answer",
    "data",
    "key_points",
    "skills",
    "sources",
    "evidence",
    "metadata",
}


def configured_ollama(monkeypatch):
    settings = get_settings().model_copy(
        update={"llm_provider": "ollama", "rag_reranker": "hybrid"}
    )
    monkeypatch.setattr(service, "get_settings", lambda: settings)


def no_llm(monkeypatch):
    factory = MagicMock(side_effect=AssertionError("This request must not call the LLM"))
    monkeypatch.setattr(service, "get_client", factory)
    return factory


def assert_quote_sources(body):
    evidence = {item["source_id"]: item for item in body["evidence"]}
    assert body["metadata"]["claims"]
    for claim in body["metadata"]["claims"]:
        assert claim["source_id"] in evidence
        assert claim["quote"] in evidence[claim["source_id"]]["chunk_text"]
    assert all(
        source["source_url"].startswith("https://example.org/test/") for source in body["sources"]
    )


def assert_measured_timings(response):
    timings = response.json()["metadata"]["timings_ms"]
    assert math.isfinite(timings["total"]) and timings["total"] >= 0
    serialization = float(response.headers["X-Serialization-Time-Ms"])
    assert math.isfinite(serialization) and serialization >= 0
    assert math.isfinite(float(response.headers["X-Response-Time"]))
    server_timing = response.headers["Server-Timing"]
    assert re.search(r"\bserializ(?:e|ation);dur=\d", server_timing)


def test_query_contract_omission_and_null_preserve_configured_default():
    assert QueryRequest(question=QUESTION).response_mode is None
    assert QueryRequest(question=QUESTION, response_mode=None).response_mode is None


def test_runtime_headers_identify_the_same_loaded_server(client):
    first = client.get("/health")
    second = client.get("/openapi.json")
    assert first.headers["X-App-Instance"] == second.headers["X-App-Instance"]
    assert re.fullmatch(r"[0-9a-f]{32}", first.headers["X-App-Instance"])
    assert re.fullmatch(r"[0-9a-f]{16}", first.headers["X-Code-Revision"])


@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize("invalid", ["fast", "ollama", "", 1, {}])
def test_invalid_response_mode_is_rejected(client, monkeypatch, endpoint, invalid):
    factory = no_llm(monkeypatch)
    response = client.post(endpoint, json={"question": QUESTION, "response_mode": invalid})
    assert response.status_code == 422
    factory.assert_not_called()


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_explicit_extractive_forwards_filters_and_never_generates(client, monkeypatch, endpoint):
    configured_ollama(monkeypatch)
    factory = no_llm(monkeypatch)
    response = client.post(
        endpoint, json={"question": QUESTION, "filters": FILTERS, "response_mode": "extractive"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert ANSWER_FIELDS <= body.keys()
    assert body["route"] == "rag"
    assert body["metadata"]["requested_mode"] == "extractive"
    assert body["metadata"]["mode"] == "extractive"
    assert body["metadata"]["output_mode"] == "extractive_quotes"
    assert body["metadata"]["generation_attempted"] is False
    assert body["metadata"]["generation_used"] is False
    assert all(item["country"] == "France" for item in body["evidence"])
    assert all(item["job_id"] == "1" for item in body["evidence"])
    assert all(claim["text"] == claim["quote"] for claim in body["metadata"]["claims"])
    assert body["metadata"]["timings_ms"]["llm_generation"] is None
    factory.assert_not_called()
    assert_quote_sources(body)
    assert_measured_timings(response)


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_explicit_generative_uses_verified_claim_and_preserves_response_shape(
    client, monkeypatch, endpoint
):
    configured_ollama(monkeypatch)

    def generate(instructions, content, schema, **kwargs):
        evidence = json.loads(content.partition("Evidence JSON: ")[2])
        source = evidence[0]
        quote = "Design Python data pipelines with SQL and Airflow."
        assert quote in source["text"]
        return GeneratedAnswer.model_validate(
            {
                "claims": [
                    {
                        "text": "This posting states: " + quote,
                        "quote": quote,
                        "source_id": source["source_id"],
                    }
                ],
                "insufficient_evidence": False,
            }
        ), {"input_tokens": 40, "output_tokens": 20}

    client_stub = SimpleNamespace(generate_structured=MagicMock(side_effect=generate))
    monkeypatch.setattr(service, "get_client", lambda: client_stub)
    response = client.post(
        endpoint, json={"question": QUESTION, "filters": FILTERS, "response_mode": "generative"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert ANSWER_FIELDS <= body.keys()
    assert body["metadata"]["requested_mode"] == "generative"
    assert body["metadata"]["mode"] == "ollama"
    assert body["metadata"]["output_mode"] == "generated_synthesis"
    assert body["metadata"]["generation_attempted"] is True
    assert body["metadata"]["generation_used"] is True
    assert body["metadata"]["grounding"]["semantic_entailment_verified"] is False
    assert body["metadata"]["usage"]["output_tokens"] == 20
    assert body["metadata"]["filters"]["country"] == "France"
    client_stub.generate_structured.assert_called_once()
    assert_quote_sources(body)
    assert_measured_timings(response)


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_generation_failure_has_truthful_extractive_fallback(client, monkeypatch, endpoint):
    configured_ollama(monkeypatch)
    client_stub = SimpleNamespace(
        generate_structured=MagicMock(side_effect=RuntimeError("Mock provider unavailable"))
    )
    monkeypatch.setattr(service, "get_client", lambda: client_stub)
    response = client.post(
        endpoint, json={"question": QUESTION, "filters": FILTERS, "response_mode": "generative"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    metadata = body["metadata"]
    assert metadata["mode"] == "extractive_fallback"
    assert metadata["output_mode"] == "extractive_quotes"
    assert metadata["generation_attempted"] is True
    assert metadata["generation_used"] is False
    assert metadata["fallback_reason"] and metadata["warning"]
    assert all(claim["text"] == claim["quote"] for claim in metadata["claims"])
    assert_quote_sources(body)


@pytest.mark.parametrize("mode", [None, "extractive", "generative"])
def test_numeric_questions_always_use_sql_without_generation(client, monkeypatch, mode):
    configured_ollama(monkeypatch)
    factory = no_llm(monkeypatch)
    response = client.post(
        "/api/assistant/query",
        json={"question": "How many jobs are in France?", "response_mode": mode},
    )
    assert response.status_code == 200
    assert response.json()["route"] == "analytics"
    assert response.json()["data"]["total_jobs"] == 2
    factory.assert_not_called()


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_no_evidence_is_honest_and_does_not_attempt_generation(client, monkeypatch, endpoint):
    configured_ollama(monkeypatch)
    factory = no_llm(monkeypatch)
    response = client.post(
        endpoint,
        json={
            "question": "Describe data jobs on Neptune",
            "filters": {"country": "Neptune"},
            "response_mode": "extractive",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["insufficient_evidence"] is True
    assert body["metadata"]["output_mode"] == "insufficient_evidence"
    assert body["metadata"]["generation_attempted"] is False
    assert body["metadata"]["generation_used"] is False
    assert not body["sources"] and not body["metadata"]["claims"]
    assert "enough evidence" in body["answer"].lower()
    factory.assert_not_called()
    assert_measured_timings(response)


@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize("include_null", [False, True])
def test_legacy_calls_preserve_configured_strict_behavior(
    client, monkeypatch, endpoint, include_null
):
    configured_ollama(monkeypatch)

    def generate(instructions, content, schema, **kwargs):
        source = json.loads(content.partition("Evidence JSON: ")[2])[0]
        quote = source["text"].split(". ", 1)[0].rstrip(".") + "."
        return GeneratedAnswer.model_validate(
            {
                "claims": [
                    {
                        "text": "Unsupported paraphrase",
                        "quote": quote,
                        "source_id": source["source_id"],
                    }
                ],
                "insufficient_evidence": False,
            }
        ), {}

    monkeypatch.setattr(
        service, "get_client", lambda: SimpleNamespace(generate_structured=generate)
    )
    payload = {"question": QUESTION, "filters": FILTERS}
    if include_null:
        payload["response_mode"] = None
    response = client.post(endpoint, json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert ANSWER_FIELDS <= body.keys()
    assert body["metadata"]["requested_mode"] is None
    assert body["metadata"]["output_mode"] == "llm_selected_quotes"
    assert body["metadata"]["mode"] == "ollama"
    assert all(claim["text"] == claim["quote"] for claim in body["metadata"]["claims"])
    assert "Unsupported paraphrase" not in body["answer"]
    assert_quote_sources(body)
