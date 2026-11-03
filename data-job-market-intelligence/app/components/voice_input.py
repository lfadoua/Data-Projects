"""Optional microphone -> editable draft -> explicit question submission."""

import hashlib
import inspect

import streamlit as st

from app.voice_transcription import MAX_AUDIO_BYTES, VoiceInputError, availability_error, transcribe


def _remember_edit():
    st.session_state["voice_draft"] = st.session_state["voice_edit"]


def _clear_draft():
    st.session_state.pop("voice_draft", None)
    st.session_state.pop("voice_error", None)
    st.session_state["voice_epoch"] = st.session_state.get("voice_epoch", 0) + 1
    st.session_state["voice_panel_epoch"] = st.session_state.get("voice_panel_epoch", 0) + 1


def render_voice_input(audio=None, *, native_capture=False, prefix=""):
    """Return text only on an explicit click; never return a recording object."""
    if native_capture:
        if audio is None and not any(
            key in st.session_state for key in ("voice_draft", "voice_error")
        ):
            return None
        with st.container(key="voice_review"):
            return _render_review(audio, prefix=prefix)

    # Compatibility path for Streamlit versions without an inline chat microphone.
    panel_options = {"icon": ":material/mic:"}
    if "key" in inspect.signature(st.popover).parameters:
        # Keep the panel open for transcription/editing; close it after send/discard.
        panel_options["key"] = f"voice_panel_{st.session_state.get('voice_panel_epoch', 0)}"
    with st.popover("Voice input · English", **panel_options):
        st.caption(
            "Record a short question (up to 30 seconds), stop, then review the text. "
            "Nothing is submitted automatically."
        )
        if not callable(getattr(st, "audio_input", None)):
            st.info(
                "Microphone input is unavailable in this Streamlit version. Please use text input."
            )
            return None
        issue = availability_error()
        if issue:
            st.info(issue)
        epoch = st.session_state.setdefault("voice_epoch", 0)
        try:
            options = {"key": f"voice_recording_{epoch}", "disabled": bool(issue)}
            if "sample_rate" in inspect.signature(st.audio_input).parameters:
                options["sample_rate"] = 16000
            audio = st.audio_input(
                "Record an English question",
                **options,
            )
        except (PermissionError, OSError):
            audio = None
            st.warning(
                "Microphone unavailable or permission denied. "
                "Allow microphone access or use text input."
            )
        with st.expander("Microphone blocked or unavailable?"):
            st.write(
                "Allow microphone access when your browser asks. If access was denied, "
                "review this site's microphone permission and reload the page. "
                "Check that a microphone is connected and selected."
            )
            st.caption(
                "Use localhost on this PC, or HTTPS for a remote server. "
                "You can always type in the question box."
            )
        st.caption(
            "Offline transcription on this Streamlit server. Audio is temporary and is not "
            "saved by the application or sent to a speech API. English only."
        )
        question = _render_review(audio)
        if "voice_draft" not in st.session_state and not st.session_state.get("voice_error"):
            st.caption("No recording yet. Press the microphone, speak, then stop recording.")
        return question


def _render_review(audio, prefix=""):
    if audio is not None:
        try:
            if audio.size > MAX_AUDIO_BYTES:
                raise VoiceInputError(
                    "The recording is too large. Keep your question under 30 seconds."
                )
            raw = audio.getvalue()
            digest = hashlib.sha256(raw).hexdigest()
            if digest != st.session_state.get("voice_audio_hash"):
                # Mark before decoding, including failures, to avoid duplicate work.
                st.session_state["voice_audio_hash"] = digest
                st.session_state.pop("voice_draft", None)
                with st.spinner("Transcribing your recording locally…"):
                    text = transcribe(raw)
                text = f"{prefix.strip()}\n{text}" if prefix.strip() else text
                if len(text) > 2000:
                    raise VoiceInputError(
                        "The combined question is too long. Use a shorter recording."
                    )
                st.session_state["voice_draft"] = text
                st.session_state["voice_edit"] = text
                st.session_state.pop("voice_error", None)
        except VoiceInputError as exc:
            st.session_state.pop("voice_draft", None)
            st.session_state["voice_error"] = str(exc)
        except (OSError, ValueError, TypeError):
            st.session_state.pop("voice_draft", None)
            st.session_state["voice_error"] = (
                "The recording could not be read. Try a new recording or type your question."
            )
        finally:
            st.session_state["voice_epoch"] = st.session_state.get("voice_epoch", 0) + 1
        st.rerun()
    if st.session_state.get("voice_error"):
        st.warning(st.session_state["voice_error"])
    if "voice_draft" not in st.session_state:
        return None
    st.session_state.setdefault("voice_edit", st.session_state["voice_draft"])
    text = st.text_area(
        "Review and edit your question",
        key="voice_edit",
        max_chars=2000,
        on_change=_remember_edit,
        help="Correct names and technical terms. "
        "Sending uses the current filters and response mode.",
    )
    st.caption(
        "Check the transcription before sending. English only; nothing is sent automatically."
    )
    send, discard = st.columns(2)
    with send:
        confirmed = st.button(
            "Send question", key="voice_send", type="primary", disabled=len(text.strip()) < 3
        )
    with discard:
        abandoned = st.button("Discard transcription", key="voice_discard")
    if abandoned:
        _clear_draft()
        st.rerun()
    if confirmed:
        question = text.strip()
        _clear_draft()
        return question
    return None
