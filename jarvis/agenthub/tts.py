from __future__ import annotations

import base64
import subprocess
import sys
import threading


_SPEECH_LOCK = threading.Lock()
_SPEECH_PROCESS: subprocess.Popen[bytes] | None = None


def speech_supported() -> bool:
    return sys.platform.startswith("win")


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


def speak_text(text: str, *, voice: str | None = None, rate: int = 0) -> bool:
    global _SPEECH_PROCESS
    if not speech_supported():
        return False

    clean = " ".join(text.strip().split())
    if not clean:
        return False

    safe_text = clean.replace("'", "''")
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