"""Optional offline English STT. Audio stays in memory; only the model is cached."""

import importlib.util
import io
import json
import os
import threading
import wave
from functools import lru_cache
from pathlib import Path

SAMPLE_RATE = 16000
MAX_SECONDS = 30
MAX_AUDIO_BYTES = 1_100_000
MODEL_NAME = "vosk-model-small-en-us-0.15"
DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[1] / "data/models" / MODEL_NAME
_model_lock = threading.Lock()


class VoiceInputError(Exception):
    """A fixed, user-safe message; decoder details and audio are never logged."""


def model_path():
    return Path(os.environ.get("DJMI_VOICE_MODEL_PATH") or DEFAULT_MODEL_PATH).expanduser()


def availability_error():
    if importlib.util.find_spec("vosk") is None:
        return "Voice input is not installed on this server. You can still type your question."
    path = model_path()
    if not (path / "am/final.mdl").is_file() or not (path / "conf/mfcc.conf").is_file():
        return "The offline English voice model is not set up. You can still type your question."
    return None


@lru_cache(maxsize=1)
def _cached_model(path):
    # An explicit path avoids Vosk's language/name-based automatic downloads.
    from vosk import Model, SetLogLevel

    SetLogLevel(-1)
    return Model(str(path))


def _get_model():
    with _model_lock:
        return _cached_model(str(model_path().resolve()))


def _read_pcm(audio):
    if not isinstance(audio, bytes) or not audio:
        raise VoiceInputError("No audio was received. Record a question, then stop recording.")
    if len(audio) > MAX_AUDIO_BYTES:
        raise VoiceInputError(
            "The recording is too large. Record a question of 30 seconds or less."
        )
    try:
        with wave.open(io.BytesIO(audio), "rb") as wav:
            if (
                wav.getnchannels() != 1
                or wav.getsampwidth() != 2
                or wav.getframerate() != SAMPLE_RATE
                or wav.getcomptype() != "NONE"
            ):
                raise VoiceInputError(
                    "Unsupported audio format. Make a new recording with the microphone."
                )
            frames = wav.getnframes()
            if frames == 0:
                raise VoiceInputError("The recording is empty. Please record your question again.")
            if frames > SAMPLE_RATE * MAX_SECONDS:
                raise VoiceInputError(
                    "The recording is too long. Keep your question under 30 seconds."
                )
            pcm = wav.readframes(frames)
            if len(pcm) != frames * 2:
                raise VoiceInputError(
                    "The recording is incomplete. Please record your question again."
                )
    except (wave.Error, EOFError, OSError, ValueError):
        raise VoiceInputError(
            "The recording could not be read. Please record your question again."
        ) from None
    if not any(pcm):
        raise VoiceInputError("No speech was detected. Check your microphone and try again.")
    return pcm


def transcribe(audio):
    """Decode one bounded WAV recording without saving audio, text, or exceptions."""
    pcm = _read_pcm(audio)
    issue = availability_error()
    if issue:
        raise VoiceInputError(issue)
    try:
        from vosk import KaldiRecognizer

        recognizer = KaldiRecognizer(_get_model(), SAMPLE_RATE)
        parts = []
        for offset in range(0, len(pcm), 8000):
            if recognizer.AcceptWaveform(pcm[offset : offset + 8000]):
                parts.append(json.loads(recognizer.Result()).get("text", ""))
        parts.append(json.loads(recognizer.FinalResult()).get("text", ""))
        text = " ".join(" ".join(parts).split())
    except Exception:
        # Never expose native decoder errors, recording contents, or local paths.
        raise VoiceInputError(
            "Transcription failed. Try another recording or type your question."
        ) from None
    if not text:
        raise VoiceInputError("No speech was detected. Speak clearly in English and try again.")
    if len(text) > 2000:
        raise VoiceInputError("The transcription is too long. Please record a shorter question.")
    return text
