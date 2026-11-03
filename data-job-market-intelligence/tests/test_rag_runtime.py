"""Runtime guards, actual provenance, and provider budgets without external services."""

from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from src.analytics.schemas import Filters
from src.config.settings import Settings, get_settings
from src.llm import client as llm
from src.llm.structured_output import GeneratedAnswer, GeneratedSummary
from src.rag import retriever, service


@pytest.mark.parametrize("structured", [False, True])
def test_output_budget_and_provider_durations_are_measured(monkeypatch, structured):
    settings = Settings(llm_model="local-test", ollama_num_gpu=0, ollama_num_predict=512)
    monkeypatch.setattr(llm, "get_settings", lambda: settings)

    def post(url, **kwargs):
        assert kwargs["json"]["options"]["num_predict"] == 512
        assert kwargs["json"]["options"]["num_gpu"] == 0
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "response": '{"claims":[],"insufficient_evidence":true}' if structured else "Hello",
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 50,
                "eval_count": 12,
                "total_duration": 9_000_000,
                "load_duration": 1_000_000,
                "prompt_eval_duration": 2_000_000,
                "eval_duration": 6_000_000,
            },
        )

    monkeypatch.setattr(httpx, "post", post)
    if structured:
        _, usage = llm.OllamaClient().generate_structured("rules", "evidence", GeneratedAnswer)
    else:
        _, usage = llm.OllamaClient().generate_text("rules", "evidence")
    assert usage["output_tokens"] == 12
    assert usage["ollama_timings_ms"] == {
        "total": 9,
        "load": 1,
        "prompt_evaluation": 2,
        "generation": 6,
    }


@pytest.mark.parametrize("failure", ["length", "invalid_json", "unfinished", "http_500"])
def test_ollama_failures_do_not_masquerade_as_completed_outputs(monkeypatch, failure):
    monkeypatch.setattr(llm, "get_settings", lambda: Settings(llm_model="local-test"))

    def post(url, **kwargs):
        return httpx.Response(
            500 if failure == "http_500" else 200,
            request=httpx.Request("POST", url),
            json={
                "response": "{"
                if failure == "invalid_json"
                else '{"claims":[],"insufficient_evidence":true}',
                "done_reason": "length" if failure == "length" else "stop",
                "done": failure != "unfinished",
                "eval_count": 23,
            },
        )

    monkeypatch.setattr(httpx, "post", post)
    exception = httpx.HTTPStatusError if failure == "http_500" else llm.GenerationOutputError
    with pytest.raises(exception) as caught:
        llm.OllamaClient().generate_structured("rules", "evidence", GeneratedAnswer)
    if failure != "http_500":
        assert caught.value.usage["output_tokens"] == 23


def test_ollama_timeout_propagates_to_safe_service_fallback(monkeypatch, indexed):
    settings = get_settings().model_copy(update={"llm_provider": "ollama"})
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    stub = SimpleNamespace(generate_structured=Mock(side_effect=httpx.ReadTimeout("timeout")))
    monkeypatch.setattr(service, "get_client", lambda: stub)
    result = service.answer_question(
        "Describe Python data pipelines",
        Filters(country="France"),
        indexed,
        response_mode="generative",
    )
    assert result.metadata["mode"] == "extractive_fallback"
    assert not result.metadata["generation_used"]
    assert result.metadata["timings_ms"]["llm_generation"] >= 0
    assert result.metadata["claims"]
    assert all(c["text"] == c["quote"] for c in result.metadata["claims"])


@pytest.mark.parametrize("mode", [None, "extractive", "generative"])
def test_empty_evidence_never_attempts_a_provider(monkeypatch, indexed, mode):
    settings = get_settings().model_copy(update={"llm_provider": "ollama"})
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    factory = Mock(side_effect=AssertionError("No evidence must mean no generation"))
    monkeypatch.setattr(service, "get_client", factory)
    result = service.answer_question(
        "Describe Data Engineer responsibilities",
        Filters(country="Neptune"),
        indexed,
        response_mode=mode,
    )
    assert result.metadata["mode"] == "extractive"
    assert result.metadata["output_mode"] == "insufficient_evidence"
    assert result.metadata["timings_ms"]["llm_generation"] is None
    assert not result.metadata["generation_attempted"]
    factory.assert_not_called()


def test_unsupported_generated_details_are_replaced_by_exact_quotes(monkeypatch, indexed):
    settings = get_settings().model_copy(update={"llm_provider": "ollama"})
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    quote = "Design Python data pipelines with SQL and Airflow."
    generated = GeneratedAnswer.model_validate(
        {
            "claims": [
                {
                    "text": "This role manages projects and guarantees regulatory compliance.",
                    "source_id": "S1",
                    "quote": quote,
                }
            ],
            "insufficient_evidence": False,
        }
    )
    stub = SimpleNamespace(generate_structured=Mock(return_value=(generated, {})))
    monkeypatch.setattr(service, "get_client", lambda: stub)
    result = service.answer_question(
        "Describe Python data pipelines",
        Filters(country="France", job_title="Data Engineer"),
        indexed,
        response_mode="generative",
    )
    assert result.metadata["mode"] == "extractive_fallback"
    assert result.metadata["grounding"]["rejected_claims"]
    assert "guarantees regulatory" not in result.answer
    assert result.sources


@pytest.mark.parametrize("unknown_source", [False, True])
def test_natural_schema_does_not_ask_model_to_copy_quotes(monkeypatch, indexed, unknown_source):
    import json

    settings = get_settings().model_copy(update={"llm_provider": "ollama"})
    monkeypatch.setattr(service, "get_settings", lambda: settings)

    def generate(instructions, content, schema):
        assert schema is GeneratedSummary
        assert "Describe Python data pipelines" not in content
        assert "COMPLETE text exactly" in instructions
        supplied = json.loads(content.partition("Evidence JSON: ")[2])
        assert set(supplied[0]) == {"text", "source_id"}
        return schema.model_validate(
            {
                "claims": [
                    {
                        "text": "This posting states: " + supplied[0]["text"],
                        "source_id": "S999" if unknown_source else supplied[0]["source_id"],
                    }
                ],
                "insufficient_evidence": False,
            }
        ), {"input_tokens": 30, "output_tokens": 20}

    monkeypatch.setattr(
        service, "get_client", lambda: SimpleNamespace(generate_structured=generate)
    )
    result = service.answer_question(
        "Describe Python data pipelines",
        Filters(country="France", job_title="Data Engineer"),
        indexed,
        response_mode="generative",
    )
    assert result.metadata["mode"] == ("extractive_fallback" if unknown_source else "ollama")
    assert result.metadata["generation_prompt_sha256"]
    assert result.metadata["generation_input_characters"] > 0
    evidence = {item["source_id"]: item for item in result.evidence}
    for claim in result.metadata["claims"]:
        assert claim["quote"] in evidence[claim["source_id"]]["chunk_text"]


@pytest.mark.parametrize("kind", ["valid_attribution", "invented_technology", "changed_quote"])
def test_observed_generation_format_keeps_grounding_closed(kind):
    from src.rag.grounding import natural_supported_claims

    quote = "Build reports and data visualizations, using data from the data warehouse."
    item = {"text": "This posting states: " + quote, "quote": quote, "source_id": "S1"}
    if kind == "invented_technology":
        item["text"] += " Deploy Kubernetes for all teams."
    elif kind == "changed_quote":
        item["quote"] = quote.replace("reports", "Kubernetes pipelines")
    accepted, rejected = natural_supported_claims(
        [item],
        [{"source_id": "S1", "chunk_text": quote}],
        "What responsibilities are expected from Senior Data Engineers?",
    )
    assert bool(accepted) is (kind == "valid_attribution")
    assert bool(rejected) is (kind != "valid_attribution")


def test_bge_reuse_does_not_skip_index_identity_checks(monkeypatch):
    retriever.bge_provider.cache_clear()
    state = SimpleNamespace(
        details={"provider": "fastembed", "space": "test-space", "dimensions": 384}
    )
    provider = SimpleNamespace(
        space="test-space",
        dimensions=384,
        embed_text=Mock(return_value=[1.0] + [0.0] * 383),
    )
    constructor = Mock(return_value=provider)
    monkeypatch.setattr(retriever, "BGEEmbeddings", constructor)
    session = Mock()
    session.get.return_value = state
    session.execute.return_value = []
    manager = Mock()
    manager.__enter__ = Mock(return_value=session)
    manager.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(retriever, "Session", lambda _: manager)
    engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    try:
        for _ in range(2):
            timings = {}
            retriever.retrieve("Python pipelines", Filters(), engine, timings=timings)
            assert timings["model_acquisition"] >= 0
            assert timings["query_embedding"] >= 0
        assert constructor.call_count == 1
        state.details = {**state.details, "space": "different-index"}
        with pytest.raises(ValueError, match="differs from the index"):
            retriever.retrieve("Python pipelines", Filters(), engine)
        assert provider.embed_text.call_count == 2
    finally:
        retriever.bge_provider.cache_clear()


def test_legacy_synthesis_keeps_distinct_labels_supported_by_the_same_quote(monkeypatch, indexed):
    quote = "Design Python data pipelines with SQL and Airflow."
    claims = [
        {"text": label, "source_id": "S1", "quote": quote} for label in ("Data pipelines", "SQL")
    ]
    legacy_answer = "Legacy theme answer [S1]."
    monkeypatch.setattr(service, "synthesize", lambda *_: (legacy_answer, [legacy_answer], claims))
    result = service.answer_question(
        "Describe Python data pipelines",
        Filters(country="France", job_title="Data Engineer"),
        indexed,
    )
    assert result.answer == legacy_answer
    assert result.metadata["claims"] == claims
    assert result.metadata["output_mode"] == "extractive_synthesis"
