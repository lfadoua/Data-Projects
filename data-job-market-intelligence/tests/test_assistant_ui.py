"""Offline assistant UI contract checks; no backend, browser, or model calls."""

import runpy
import sys
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.components import design, ui, voice_input


class SessionState(dict):
    def __getattr__(self, name):
        return self[name]

    def __setattr__(self, name, value):
        self[name] = value


@pytest.fixture
def fake_streamlit(monkeypatch):
    fake = MagicMock()
    fake.session_state = SessionState()
    fake.columns.side_effect = lambda spec, **kwargs: [
        nullcontext() for _ in range(spec if isinstance(spec, int) else len(spec))
    ]
    fake.expander.side_effect = lambda *args, **kwargs: nullcontext()
    fake.chat_message.side_effect = lambda *args, **kwargs: nullcontext()
    fake.spinner.side_effect = lambda *args, **kwargs: nullcontext()
    fake.button.return_value = False
    fake.chat_input.return_value = None
    monkeypatch.setattr(ui, "st", fake)
    monkeypatch.setattr(ui, "preferences", lambda: {"show_technical": False})
    monkeypatch.setattr(ui, "chips", MagicMock())
    monkeypatch.setattr(voice_input, "render_voice_input", lambda: None)
    return fake


@pytest.mark.parametrize("mode", [None, "extractive", "generative"])
def test_assistant_page_sends_mode_and_filters(monkeypatch, fake_streamlit, mode):
    question = "Describe Python responsibilities"
    filters = {"country": "France", "skill": "Python"}
    fake_streamlit.session_state.update(assistant_response_mode=mode, pending_question=question)
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    monkeypatch.setattr(ui, "setup", MagicMock())
    monkeypatch.setattr(ui, "filters_panel", lambda: filters)
    monkeypatch.setattr(design, "panel", lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(design, "section", MagicMock())
    monkeypatch.setattr(design, "empty_state", MagicMock())
    result = {"route": "rag", "answer": "Build Python pipelines. [S1]"}
    mocked_request = MagicMock(return_value=result)
    monkeypatch.setattr(ui, "request", mocked_request)

    runpy.run_path(str(Path(ui.ROOT) / "app/pages/3_AI_Assistant.py"))

    expected = {"question": question, "filters": filters}
    if mode is not None:
        expected["response_mode"] = mode
    mocked_request.assert_called_once_with("/api/assistant/query", body=expected)
    assert fake_streamlit.session_state["messages"][-1]["content"] == result
    assert filters == {"country": "France", "skill": "Python"}
    assert "2024" in fake_streamlit.caption.call_args_list[0].args[0]
    assert fake_streamlit.spinner.call_args.args[0] == ui.assistant_wait_message(mode)


def test_response_mode_survives_widget_cleanup(fake_streamlit):
    assert ui.response_mode_selector() == "extractive"
    fake_streamlit.session_state["_assistant_response_mode"] = "generative"
    fake_streamlit.selectbox.call_args.kwargs["on_change"]()
    del fake_streamlit.session_state["_assistant_response_mode"]

    assert ui.response_mode_selector() == "generative"
    assert fake_streamlit.session_state["_assistant_response_mode"] == "generative"


def test_configured_default_is_a_visible_option_and_omits_override(fake_streamlit):
    ui.response_mode_selector()
    widget = fake_streamlit.selectbox.call_args
    assert None not in widget.args[1]
    assert widget.kwargs["format_func"]("configured") == "Configured default"
    fake_streamlit.session_state["_assistant_response_mode"] = "configured"
    widget.kwargs["on_change"]()
    assert "response_mode" not in ui.assistant_body(
        "Describe data jobs", {}, fake_streamlit.session_state["assistant_response_mode"]
    )


def test_failed_request_requires_manual_retry_and_preserves_original_context(
    monkeypatch, fake_streamlit
):
    """An unavailable API must not loop or silently use newly selected filters."""
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    monkeypatch.setattr(ui, "setup", MagicMock())
    filters = {"country": "France"}
    monkeypatch.setattr(ui, "filters_panel", lambda: filters)
    monkeypatch.setattr(design, "panel", lambda *args, **kwargs: nullcontext())
    failed = MagicMock(return_value=None)
    monkeypatch.setattr(ui, "request", failed)
    question = "Describe Python responsibilities"
    fake_streamlit.session_state.update(
        pending_question=question, assistant_response_mode="generative"
    )
    page = str(Path(ui.ROOT) / "app/pages/3_AI_Assistant.py")
    runpy.run_path(page)
    original_body = {
        "question": question,
        "filters": {"country": "France"},
        "response_mode": "generative",
    }
    assert fake_streamlit.session_state["assistant_failed_request"] == original_body
    assert len(fake_streamlit.session_state["messages"]) == 1

    # A routine rerun must not repeat a slow or potentially chargeable request.
    failed.reset_mock()
    filters["country"] = "Canada"
    fake_streamlit.session_state["assistant_response_mode"] = "extractive"
    runpy.run_path(page)
    failed.assert_not_called()

    result = {"route": "rag", "answer": "Actual source text [S1]"}
    failed.return_value = result
    fake_streamlit.button.side_effect = lambda label, **kwargs: label == "Retry last question"
    runpy.run_path(page)
    failed.assert_called_once_with("/api/assistant/query", body=original_body)
    assert "assistant_failed_request" not in fake_streamlit.session_state
    assert [m["role"] for m in fake_streamlit.session_state["messages"]] == ["user", "assistant"]


def test_assistant_empty_state_does_not_call_api_and_always_renders_input(
    monkeypatch, fake_streamlit
):
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    monkeypatch.setattr(ui, "setup", MagicMock())
    monkeypatch.setattr(ui, "filters_panel", lambda: {})
    monkeypatch.setattr(design, "panel", lambda *args, **kwargs: nullcontext())
    request = MagicMock()
    monkeypatch.setattr(ui, "request", request)
    runpy.run_path(str(Path(ui.ROOT) / "app/pages/3_AI_Assistant.py"))
    request.assert_not_called()
    fake_streamlit.chat_input.assert_called_once()
    assert any("[S1]" in str(call) for call in fake_streamlit.caption.call_args_list)


def test_request_posts_the_explicit_mode_without_changing_filters(monkeypatch, fake_streamlit):
    client = MagicMock()
    factory = MagicMock()
    factory.return_value.__enter__.return_value = client
    client.post.return_value.json.return_value = {"route": "rag", "answer": "Evidence"}
    monkeypatch.setattr(ui.httpx, "Client", factory)
    monkeypatch.setattr(ui, "api_url", lambda: "http://ui.test")
    filters = {"country": "France"}

    assert (
        ui.request(
            "/api/assistant/query",
            body=ui.assistant_body("Describe data jobs", filters, "extractive"),
        )["route"]
        == "rag"
    )

    client.post.assert_called_once_with(
        "http://ui.test/api/assistant/query",
        json={
            "question": "Describe data jobs",
            "filters": {"country": "France"},
            "response_mode": "extractive",
        },
    )
    assert filters == {"country": "France"}
    fake_streamlit.error.assert_not_called()


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        ({}, ""),
        ({"mode": "ollama", "latency_seconds": 9.25}, "Ollama · 9.2 s"),
        (
            {
                "mode": "extractive",
                "output_mode": "extractive_quotes",
                "generation_attempted": False,
                "timings_ms": {"total": 125},
                "latency_seconds": 99,
            },
            "Extractive · Exact quotes · 0.12 s",
        ),
        (
            {
                "mode": "extractive_fallback",
                "output_mode": "extractive_quotes",
                "requested_mode": "generative",
                "generation_attempted": True,
            },
            "Extractive fallback · Exact quotes",
        ),
        (
            {
                "mode": "ollama",
                "output_mode": "generated_synthesis",
                "generation_attempted": True,
            },
            "Ollama · Natural synthesis",
        ),
        (
            {"mode": "openai", "output_mode": "llm_selected_quotes"},
            "OpenAI · Exact quotes",
        ),
        (
            {"mode": "ollama", "generation_attempted": False, "insufficient_evidence": True},
            "Insufficient evidence · No LLM call",
        ),
    ],
)
def test_answer_caption_uses_actual_output_and_measured_time(metadata, expected):
    assert ui.answer_caption(metadata) == expected


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -1, True, "12", None])
def test_invalid_total_time_uses_valid_legacy_measurement(invalid):
    assert ui.answer_caption({"timings_ms": {"total": invalid}, "latency_seconds": 1.5}) == "1.5 s"
    assert ui.answer_caption({"timings_ms": {"total": invalid}, "latency_seconds": invalid}) == ""


def test_zero_duration_is_valid():
    assert ui.answer_caption({"timings_ms": {"total": 0}}) == "0.00 s"


def test_render_old_answer_preserves_citations(fake_streamlit):
    response = {"route": "rag", "answer": "Supported text. [S1]\n• Another point. [S2]"}
    ui.render_answer(response, show_sources=False)

    fake_streamlit.markdown.assert_called_once_with("Supported text. [S1]\n\n- Another point. [S2]")
    fake_streamlit.warning.assert_not_called()
    fake_streamlit.json.assert_not_called()


def test_render_fallback_and_guard_without_claiming_semantic_proof(fake_streamlit, monkeypatch):
    metadata = {
        "requested_mode": "generative",
        "mode": "extractive_fallback",
        "output_mode": "extractive_quotes",
        "generation_attempted": True,
        "generation_used": False,
        "fallback_reason": "unsupported_claims",
        "warning": "Detailed reason kept in the technical view.",
        "timings_ms": {"total": 12},
        "grounding": {
            "strategy": "conservative_paraphrase",
            "source_ids_validated": True,
            "exact_quotes_validated": True,
            "semantic_entailment_verified": False,
            "rejected_claims": 1,
        },
    }
    monkeypatch.setattr(ui, "preferences", lambda: {"show_technical": True})
    ui.render_answer(
        {"route": "rag", "answer": "A source quote. [S1]", "metadata": metadata}, show_sources=False
    )

    captions = " ".join(call.args[0] for call in fake_streamlit.caption.call_args_list)
    assert "Extractive fallback" in captions and "Ollama" not in captions
    assert "paraphrases need review" in captions
    assert "semantically verified" not in captions.lower()
    assert "extractive fallback" in fake_streamlit.warning.call_args.args[0]
    assert fake_streamlit.json.call_args.args[0]["grounding"] == metadata["grounding"]
    assert fake_streamlit.json.call_args.args[0]["fallback_reason"] == "unsupported_claims"


def test_incomplete_guard_is_not_reported_as_passed(fake_streamlit):
    ui.render_answer(
        {
            "route": "rag",
            "answer": "An answer.",
            "metadata": {"grounding": {"strategy": "conservative_paraphrase"}},
        },
        show_sources=False,
    )
    assert not any(
        "checks passed" in call.args[0] for call in fake_streamlit.caption.call_args_list
    )


def test_sources_empty_state_distinguishes_cited_from_retrieved(monkeypatch, fake_streamlit):
    empty = MagicMock()
    monkeypatch.setattr(ui, "empty_state", empty)
    ui.sources_panel({"sources": [], "evidence": [{"source_id": "S1", "chunk_text": "Text"}]})
    assert empty.call_args.args[0] == "No cited sources"


def test_sources_show_the_complete_returned_passage(fake_streamlit):
    passage = "A supported statement. " * 40 + "The cited text at the end."
    ui.sources_panel(
        {
            "sources": [{"source_id": "S1", "job_title": "Engineer", "excerpt": passage[:320]}],
            "evidence": [{"source_id": "S1", "chunk_text": passage}],
        }
    )
    fake_streamlit.write.assert_called_once_with(passage)


def test_insufficient_evidence_is_explained_without_changing_the_refusal(fake_streamlit):
    refusal = "Insufficient evidence in the selected records."
    ui.render_answer(
        {"route": "rag", "answer": refusal, "metadata": {"insufficient_evidence": True}},
        show_sources=False,
    )
    fake_streamlit.markdown.assert_called_once_with(refusal)
    assert "not enough matching evidence" in fake_streamlit.warning.call_args.args[0]


def test_preview_defaults_to_extraction_and_cache_separates_modes(monkeypatch):
    response = MagicMock()
    response.json.side_effect = [{"answer": "exact quote"}, {"answer": "generated"}]
    post = MagicMock(return_value=response)
    monkeypatch.setattr(ui.httpx, "post", post)
    ui.assistant_preview.clear()
    try:
        assert ui.assistant_preview("http://ui.test", (("country", "France"),), "v2") == {
            "answer": "exact quote"
        }
        ui.assistant_preview("http://ui.test", (("country", "France"),), "v2")
        assert post.call_count == 1
        assert post.call_args.kwargs["json"]["response_mode"] == "extractive"
        assert post.call_args.kwargs["json"]["filters"] == {"country": "France"}
        assert ui.assistant_preview(
            "http://ui.test", (("country", "France"),), "v2", response_mode="generative"
        ) == {"answer": "generated"}
        assert post.call_count == 2
    finally:
        ui.assistant_preview.clear()
