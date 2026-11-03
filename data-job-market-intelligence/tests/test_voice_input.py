"""Offline speech/UI contracts; no microphone, external services or model downloads."""

import hashlib
import io
import json
import runpy
import struct
import sys
import wave
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app import voice_transcription as stt
from app.components import design, ui, voice_input


class Rerun(BaseException):
    pass


def wav_bytes(frames=8000, value=500, channels=1, rate=16000, width=2):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(
            struct.pack("<h", value) * frames * channels if width == 2 else b"x" * frames
        )
    return stream.getvalue()


@pytest.fixture
def voice_ui(monkeypatch):
    fake = MagicMock()
    fake.session_state = {}
    for method in ("popover", "expander", "spinner", "chat_message", "container"):
        getattr(fake, method).side_effect = lambda *args, **kwargs: nullcontext()
    fake.columns.side_effect = lambda spec, **kwargs: [
        nullcontext() for _ in range(spec if isinstance(spec, int) else len(spec))
    ]
    fake.audio_input.return_value = None
    fake.chat_input.return_value = None
    fake.button.return_value = False
    fake.text_area.side_effect = lambda *args, **kwargs: fake.session_state["voice_edit"]
    fake.rerun.side_effect = Rerun
    monkeypatch.setattr(voice_input, "st", fake)
    monkeypatch.setattr(voice_input, "availability_error", lambda: None)
    return fake


@pytest.fixture
def decoder(monkeypatch):
    recognizer = MagicMock()
    recognizer.AcceptWaveform.return_value = False
    recognizer.FinalResult.return_value = json.dumps(
        {"text": "what percentage of jobs mention python"}
    )
    monkeypatch.setitem(
        sys.modules, "vosk", SimpleNamespace(KaldiRecognizer=lambda *args: recognizer)
    )
    monkeypatch.setattr(stt, "availability_error", lambda: None)
    monkeypatch.setattr(stt, "_get_model", lambda: object())
    return recognizer


def test_successful_transcription_is_in_memory_and_does_not_log(
    monkeypatch, decoder, capsys, caplog
):
    recording = wav_bytes()
    forbidden_write = MagicMock(side_effect=AssertionError("Audio must not be written"))
    with monkeypatch.context() as patch:
        patch.setattr("builtins.open", forbidden_write)
        assert stt.transcribe(recording) == "what percentage of jobs mention python"
    forbidden_write.assert_not_called()
    assert not caplog.records
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_recognizer_keeps_completed_and_final_segments(decoder):
    decoder.AcceptWaveform.side_effect = [True, False]
    decoder.Result.return_value = '{"text":"what percentage"}'
    decoder.FinalResult.return_value = '{"text":"of jobs mention python"}'
    assert stt.transcribe(wav_bytes()) == "what percentage of jobs mention python"


@pytest.mark.parametrize(
    ("recording", "message"),
    [
        (b"", "No audio"),
        (b"not a wave file", "could not be read"),
        (wav_bytes(frames=0), "empty"),
        (wav_bytes(value=0), "No speech"),
        (wav_bytes(channels=2), "Unsupported audio"),
        (wav_bytes(rate=44100), "Unsupported audio"),
        (wav_bytes(width=1), "Unsupported audio"),
        (wav_bytes()[:-8], "incomplete"),
        (wav_bytes(frames=16000 * 31), "too long"),
        (b"x" * (stt.MAX_AUDIO_BYTES + 1), "too large"),
    ],
    ids=[
        "no-audio",
        "not-wav",
        "empty-wav",
        "silence",
        "stereo",
        "wrong-rate",
        "wrong-width",
        "truncated",
        "too-long",
        "too-large",
    ],
)
def test_empty_invalid_or_unbounded_audio_is_rejected_before_model_load(
    monkeypatch, recording, message
):
    model = MagicMock()
    monkeypatch.setattr(stt, "_get_model", model)
    with pytest.raises(stt.VoiceInputError, match=message):
        stt.transcribe(recording)
    model.assert_not_called()


@pytest.mark.parametrize("result", ['{"text":""}', "not json", '{"text":null}'])
def test_failed_or_empty_decoder_output_is_user_safe(decoder, result):
    decoder.FinalResult.return_value = result
    with pytest.raises(stt.VoiceInputError, match="No speech|Transcription failed"):
        stt.transcribe(wav_bytes())


def test_model_failure_does_not_expose_native_error(monkeypatch, decoder):
    decoder.AcceptWaveform.side_effect = RuntimeError("private audio or host details")
    with pytest.raises(stt.VoiceInputError) as error:
        stt.transcribe(wav_bytes())
    assert "private audio" not in str(error.value)


def test_missing_optional_dependency_is_a_normal_unavailable_state(monkeypatch):
    monkeypatch.setattr(stt.importlib.util, "find_spec", lambda _: None)
    assert "not installed" in stt.availability_error()


def test_missing_model_does_not_trigger_download(monkeypatch, tmp_path):
    monkeypatch.setattr(stt.importlib.util, "find_spec", lambda _: object())
    monkeypatch.setattr(stt, "model_path", lambda: tmp_path)
    assert "not set up" in stt.availability_error()
    assert list(tmp_path.iterdir()) == []


def test_model_is_cached_without_caching_recordings(monkeypatch, tmp_path):
    model = MagicMock(return_value=object())
    monkeypatch.setitem(sys.modules, "vosk", SimpleNamespace(Model=model, SetLogLevel=MagicMock()))
    monkeypatch.setattr(stt, "model_path", lambda: tmp_path)
    stt._cached_model.cache_clear()
    try:
        assert stt._get_model() is stt._get_model()
        model.assert_called_once_with(str(tmp_path.resolve()))
    finally:
        stt._cached_model.cache_clear()


def test_recording_creates_only_a_draft_and_is_not_transcribed_again(monkeypatch, voice_ui):
    raw = wav_bytes()
    audio = SimpleNamespace(size=len(raw), getvalue=lambda: raw)
    voice_ui.audio_input.return_value = audio
    decode = MagicMock(return_value="what percentage of jobs mention python")
    monkeypatch.setattr(voice_input, "transcribe", decode)
    with pytest.raises(Rerun):
        voice_input.render_voice_input()
    assert voice_ui.session_state["voice_draft"] == "what percentage of jobs mention python"
    assert voice_ui.session_state["voice_epoch"] == 1
    assert voice_ui.session_state["voice_audio_hash"] == hashlib.sha256(raw).hexdigest()
    assert all(
        not isinstance(value, (bytes, io.BytesIO)) for value in voice_ui.session_state.values()
    )
    with pytest.raises(Rerun):
        voice_input.render_voice_input()
    decode.assert_called_once_with(raw)
    voice_ui.audio_input.return_value = None
    assert voice_input.render_voice_input() is None
    assert voice_ui.text_area.called


def test_inline_capture_has_no_extra_voice_panel_when_idle(voice_ui):
    assert voice_input.render_voice_input(native_capture=True) is None
    voice_ui.popover.assert_not_called()
    voice_ui.audio_input.assert_not_called()
    voice_ui.text_area.assert_not_called()


def test_inline_capture_preserves_text_and_requires_review(monkeypatch, voice_ui):
    raw = wav_bytes()
    audio = SimpleNamespace(size=len(raw), getvalue=lambda: raw)
    decode = MagicMock(return_value="what skills mention python")
    monkeypatch.setattr(voice_input, "transcribe", decode)
    with pytest.raises(Rerun):
        voice_input.render_voice_input(audio, native_capture=True, prefix="Senior roles:")
    assert voice_ui.session_state["voice_draft"] == "Senior roles:\nwhat skills mention python"
    assert voice_input.render_voice_input(native_capture=True) is None
    voice_ui.popover.assert_not_called()
    voice_ui.button.side_effect = lambda *args, **kwargs: kwargs.get("key") == "voice_send"
    assert voice_input.render_voice_input(native_capture=True) == (
        "Senior roles:\nwhat skills mention python"
    )
    decode.assert_called_once()


def test_editing_does_not_submit_and_explicit_send_returns_edited_text_once(voice_ui):
    voice_ui.session_state.update(
        voice_draft="old words", voice_edit="How many Data Engineer jobs are in France?"
    )
    assert voice_input.render_voice_input() is None
    voice_ui.text_area.call_args.kwargs["on_change"]()
    assert voice_ui.session_state["voice_draft"] == voice_ui.session_state["voice_edit"]
    voice_ui.button.side_effect = lambda *args, **kwargs: kwargs.get("key") == "voice_send"
    assert voice_input.render_voice_input() == "How many Data Engineer jobs are in France?"
    assert "voice_draft" not in voice_ui.session_state
    voice_ui.button.side_effect = None
    voice_ui.button.return_value = False
    assert voice_input.render_voice_input() is None


@pytest.mark.parametrize("failure", ["", "No speech was detected."])
def test_transcription_failure_does_not_retain_an_old_draft_or_retry(
    monkeypatch, voice_ui, failure
):
    raw = wav_bytes()
    voice_ui.audio_input.return_value = SimpleNamespace(size=len(raw), getvalue=lambda: raw)
    voice_ui.session_state["voice_draft"] = "An earlier question"
    decode = MagicMock(side_effect=stt.VoiceInputError(failure or "Transcription failed."))
    monkeypatch.setattr(voice_input, "transcribe", decode)
    with pytest.raises(Rerun):
        voice_input.render_voice_input()
    assert "voice_draft" not in voice_ui.session_state
    voice_ui.audio_input.return_value = None
    assert voice_input.render_voice_input() is None
    decode.assert_called_once()
    voice_ui.warning.assert_called()


@pytest.mark.parametrize("exception", [PermissionError, OSError])
def test_microphone_denied_or_missing_keeps_text_path_available(voice_ui, exception):
    voice_ui.audio_input.side_effect = exception("device details")
    assert voice_input.render_voice_input() is None
    assert "permission denied" in voice_ui.warning.call_args.args[0]


def test_streamlit_without_audio_widget_remains_usable(voice_ui):
    voice_ui.audio_input = None
    assert voice_input.render_voice_input() is None
    assert "unavailable" in voice_ui.info.call_args.args[0]


def test_native_widget_without_sample_rate_parameter_does_not_break_text_mode(voice_ui):
    calls = []

    def legacy_audio(label, *, key, disabled):
        calls.append((key, disabled))
        return None

    voice_ui.audio_input = legacy_audio
    assert voice_input.render_voice_input() is None
    assert calls == [("voice_recording_0", False)]


def test_recording_read_failure_is_a_safe_error(voice_ui):
    voice_ui.audio_input.return_value = SimpleNamespace(
        size=100, getvalue=MagicMock(side_effect=ValueError("internal details"))
    )
    with pytest.raises(Rerun):
        voice_input.render_voice_input()
    assert "could not be read" in voice_ui.session_state["voice_error"]
    assert "internal details" not in voice_ui.session_state["voice_error"]


def test_oversized_upload_is_not_copied_or_decoded(monkeypatch, voice_ui):
    voice_ui.session_state["voice_draft"] = "An earlier question"
    read = MagicMock()
    voice_ui.audio_input.return_value = SimpleNamespace(size=stt.MAX_AUDIO_BYTES + 1, getvalue=read)
    decode = MagicMock()
    monkeypatch.setattr(voice_input, "transcribe", decode)
    with pytest.raises(Rerun):
        voice_input.render_voice_input()
    read.assert_not_called()
    decode.assert_not_called()
    assert "voice_draft" not in voice_ui.session_state


def test_discard_transcription_cannot_submit(voice_ui):
    voice_ui.session_state.update(voice_draft="Some text", voice_edit="Some text")
    voice_ui.button.side_effect = lambda *args, **kwargs: kwargs.get("key") == "voice_discard"
    with pytest.raises(Rerun):
        voice_input.render_voice_input()
    assert "voice_draft" not in voice_ui.session_state


def test_real_streamlit_editor_requires_click_and_consumes_submission(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(voice_input, "availability_error", lambda: None)
    app = AppTest.from_string(
        """
import streamlit as st
from app.components.voice_input import render_voice_input
if 'seeded' not in st.session_state:
    st.session_state.update(seeded=True, voice_draft='unrecognized term', submitted=[])
question = render_voice_input()
if question is not None:
    st.session_state.submitted.append(question)
""",
        default_timeout=15,
    ).run()
    assert not app.exception
    app.text_area(key="voice_edit").input("What percentage of jobs mention Python?").run()
    assert app.session_state["submitted"] == []
    app.button(key="voice_send").click().run()
    assert not app.exception
    assert app.session_state["submitted"] == ["What percentage of jobs mention Python?"]
    app.run()
    assert app.session_state["submitted"] == ["What percentage of jobs mention Python?"]
    assert len(app.text_area) == 0


def test_real_native_chat_microphone_keeps_text_messages_functional():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_string(
        """
import streamlit as st
entry = st.chat_input('Question', key='question', accept_audio=True, audio_sample_rate=16000)
if entry:
    st.session_state.received = entry if isinstance(entry, str) else entry.text
""",
        default_timeout=15,
    ).run()
    app.chat_input(key="question").set_value("What percentage of jobs mention Python?").run()
    assert not app.exception
    assert app.session_state["received"] == "What percentage of jobs mention Python?"


class SessionState(dict):
    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value


@pytest.mark.parametrize("route", ["analytics", "rag"])
def test_inline_audio_is_transcribed_before_explicit_question_submission(
    monkeypatch, voice_ui, route
):
    raw = wav_bytes()
    audio = SimpleNamespace(size=len(raw), getvalue=lambda: raw)
    incoming = [SimpleNamespace(text="", audio=audio)]

    def native_chat(placeholder, *, max_chars, accept_audio, audio_sample_rate):
        assert accept_audio is True and audio_sample_rate == 16000
        return incoming[0]

    voice_ui.chat_input = native_chat
    voice_ui.session_state = SessionState()
    monkeypatch.setitem(sys.modules, "streamlit", voice_ui)
    monkeypatch.setattr(ui, "st", voice_ui)
    monkeypatch.setattr(ui, "setup", MagicMock())
    monkeypatch.setattr(ui, "filters_panel", lambda: {"country": "Canada"})
    monkeypatch.setattr(ui, "response_mode_selector", lambda: "extractive")
    monkeypatch.setattr(ui, "render_answer", MagicMock())
    monkeypatch.setattr(ui, "sources_panel", MagicMock())
    monkeypatch.setattr(design, "panel", lambda *args, **kwargs: nullcontext())
    question = (
        "What percentage of jobs mention Python?"
        if route == "analytics"
        else ("What responsibilities are expected from Senior Data Engineers?")
    )
    decode = MagicMock(return_value=question)
    monkeypatch.setattr(voice_input, "transcribe", decode)
    request = MagicMock(return_value={"route": route, "answer": "Existing answer [S1]"})
    monkeypatch.setattr(ui, "request", request)
    page = str(ui.ROOT / "app/pages/3_AI_Assistant.py")
    with pytest.raises(Rerun):
        runpy.run_path(page)
    request.assert_not_called()
    incoming[0] = None
    runpy.run_path(page)
    request.assert_not_called()
    voice_ui.button.side_effect = lambda *args, **kwargs: kwargs.get("key") == "voice_send"
    with pytest.raises(Rerun):
        runpy.run_path(page)
    request.assert_called_once_with(
        "/api/assistant/query",
        body={
            "question": question,
            "filters": {"country": "Canada"},
            "response_mode": "extractive",
        },
    )
    assert len(voice_ui.session_state["messages"]) == 2
    voice_ui.button.side_effect = None
    voice_ui.button.return_value = False
    runpy.run_path(page)
    assert request.call_count == 1
    decode.assert_called_once()


@pytest.mark.parametrize(
    ("question", "route"),
    [
        ("What percentage of jobs mention Python?", "analytics"),
        ("What responsibilities are expected from Senior Data Engineers?", "rag"),
    ],
)
@pytest.mark.parametrize("mode", [None, "extractive", "generative"])
def test_confirmed_voice_uses_existing_pipeline_without_duplicate_questions(
    monkeypatch, voice_ui, question, route, mode
):
    voice_ui.session_state = SessionState(voice_draft="uncorrected words", voice_edit=question)
    monkeypatch.setitem(sys.modules, "streamlit", voice_ui)
    monkeypatch.setattr(ui, "st", voice_ui)
    monkeypatch.setattr(ui, "setup", MagicMock())
    monkeypatch.setattr(ui, "filters_panel", lambda: {"country": "Canada"})
    monkeypatch.setattr(ui, "response_mode_selector", lambda: mode)
    monkeypatch.setattr(ui, "render_answer", MagicMock())
    monkeypatch.setattr(ui, "sources_panel", MagicMock())
    monkeypatch.setattr(design, "panel", lambda *args, **kwargs: nullcontext())
    response = {"route": route, "answer": "Existing pipeline answer [S1]"}
    request = MagicMock(return_value=response)
    monkeypatch.setattr(ui, "request", request)
    page = str(ui.ROOT / "app/pages/3_AI_Assistant.py")
    # An editable draft is never itself an API request.
    runpy.run_path(page)
    request.assert_not_called()
    voice_ui.button.side_effect = lambda *args, **kwargs: kwargs.get("key") == "voice_send"
    with pytest.raises(Rerun):
        runpy.run_path(page)
    body = {"question": question, "filters": {"country": "Canada"}}
    if mode is not None:
        body["response_mode"] = mode
    request.assert_called_once_with("/api/assistant/query", body=body)
    assert [m["role"] for m in voice_ui.session_state["messages"]] == ["user", "assistant"]
    assert voice_ui.session_state["messages"][0]["content"] == question
    assert voice_ui.session_state["messages"][1]["content"] is response
    voice_ui.button.side_effect = None
    voice_ui.button.return_value = False
    runpy.run_path(page)
    assert request.call_count == 1
    assert len(voice_ui.session_state["messages"]) == 2
