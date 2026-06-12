from __future__ import annotations

import base64
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

from .config import data_dir, load_config


_SPEECH_LOCK = threading.Lock()
_SPEECH_PROCESS: subprocess.Popen[bytes] | None = None
TTS_OUTPUT_DIR = data_dir() / "voice" / "tts"


def speech_supported() -> bool:
    return bool(_openai_tts_available() or sys.platform.startswith("win"))


def _encoded_command(script: str) -> str:
    return base64.b64encode(script.encode("utf-16le")).decode("ascii")


def stop_speaking() -> None:
    global _SPEECH_PROCESS
    with _SPEECH_LOCK:
        if _SPEECH_PROCESS is not None and _SPEECH_PROCESS.poll() is None:
            try:
                _SPEECH_PROCESS.terminate()
            except Exception:
                pass
        _SPEECH_PROCESS = None


def _openai_tts_available() -> bool:
    cfg = load_config()
    api_key = os.environ.get(cfg.api_key_env, "") or os.environ.get("OPENAI_API_KEY", "")
    return bool(str(api_key).strip())


def _resolve_tts_provider() -> str:
    if _openai_tts_available():
        return "openai_tts"
    if sys.platform.startswith("win"):
        return "windows_speech"
    return "none"


def _play_wav_file(path: Path) -> bool:
    script = (
        "Add-Type -AssemblyName System;"
        f"$player = New-Object System.Media.SoundPlayer('{str(path).replace("'", "''")}');"
        "$player.PlaySync();"
    )

    startupinfo = None
    creationflags = 0
    if hasattr(subprocess, "STARTUPINFO"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW

    global _SPEECH_PROCESS
    with _SPEECH_LOCK:
        if _SPEECH_PROCESS is not None and _SPEECH_PROCESS.poll() is None:
            try:
                _SPEECH_PROCESS.terminate()
            except Exception:
                pass
        _SPEECH_PROCESS = subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                _encoded_command(script),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
    return True


def _speak_with_windows(text: str, *, voice: str | None = None, rate: int = 0) -> bool:
    global _SPEECH_PROCESS
    if not sys.platform.startswith("win"):
        return False

    safe_text = text.replace("'", "''")
    safe_voice = (voice or "").replace("'", "''")
    bounded_rate = max(-10, min(10, int(rate)))
    voice_line = f"$speaker.SelectVoice('{safe_voice}');" if safe_voice else ""
    script = (
        "Add-Type -AssemblyName System.Speech;"
        "$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        f"$speaker.Rate = {bounded_rate};"
        f"{voice_line}"
        f"$speaker.Speak('{safe_text}');"
    )

    startupinfo = None
    creationflags = 0
    if hasattr(subprocess, "STARTUPINFO"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW

    with _SPEECH_LOCK:
        if _SPEECH_PROCESS is not None and _SPEECH_PROCESS.poll() is None:
            try:
                _SPEECH_PROCESS.terminate()
            except Exception:
                pass
        _SPEECH_PROCESS = subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                _encoded_command(script),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
    return True


def _speak_with_openai(text: str, *, voice: str | None = None) -> bool:
    from openai import OpenAI

    cfg = load_config()
    api_key = os.environ.get(cfg.api_key_env, "") or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return False

    client = OpenAI(api_key=api_key)
    TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=TTS_OUTPUT_DIR, suffix=".wav", delete=False) as handle:
        wav_path = Path(handle.name)

    response = None
    for model_name in ("gpt-4o-mini-tts", "tts-1-hd", "tts-1"):
        try:
            response = client.audio.speech.create(
                model=model_name,
                voice=voice or "nova",
                input=text,
                response_format="wav",
            )
            break
        except Exception:
            response = None
            continue
    if response is None:
        try:
            wav_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False

    audio_bytes = getattr(response, "content", None)
    if not audio_bytes:
        try:
            audio_bytes = response.read()
        except Exception:
            audio_bytes = b""
    if not audio_bytes:
        try:
            wav_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False

    wav_path.write_bytes(audio_bytes)
    return _play_wav_file(wav_path)


def speak_text(text: str, *, voice: str | None = None, rate: int = 0) -> bool:
    if not speech_supported():
        return False

    clean = " ".join(text.strip().split())
    if not clean:
        return False

    provider = _resolve_tts_provider()
    if provider == "openai_tts":
        if _speak_with_openai(clean, voice=voice):
            return True
        return _speak_with_windows(clean, voice=voice, rate=rate)
    if provider == "windows_speech":
        return _speak_with_windows(clean, voice=voice, rate=rate)
    return False