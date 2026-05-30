from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess
import sys
import wave

from .config import data_dir


VOICE_DIR = data_dir() / "voice"
MIC_CONFIG_PATH = VOICE_DIR / "mic_config.json"
CAPTURE_STATE_PATH = VOICE_DIR / "capture_state.json"
SPEECH_MODE_PATH = VOICE_DIR / "speech_mode.json"
RECORDINGS_DIR = VOICE_DIR / "recordings"


def _exception_chain_text(exc: BaseException) -> str:
    parts: list[str] = []
    current: BaseException | None = exc
    while current is not None:
        parts.append(str(current))
        current = current.__cause__
    return " | ".join(part for part in parts if part)


@dataclass(frozen=True)
class SpeechProvider:
    name: str
    kind: str
    description: str
    requires_network: bool


@dataclass(frozen=True)
class TranscriptionResult:
    provider: str
    transcript: str
    source: str


@dataclass(frozen=True)
class MicrophoneConfig:
    device: str
    sample_rate: int
    chunk_ms: int
    mode: str


@dataclass(frozen=True)
class CaptureState:
    active: bool
    provider: str
    mode: str


@dataclass(frozen=True)
class InputDevice:
    index: int
    name: str
    max_input_channels: int
    default_sample_rate: int


@dataclass(frozen=True)
class RecognizerInfo:
    culture: str
    name: str


@dataclass(frozen=True)
class SpeechModeConfig:
    language_mode: str
    provider: str
    culture: str


def _load_sounddevice():
    try:
        import sounddevice as sd
    except ModuleNotFoundError as exc:
        if exc.name == "sounddevice":
            raise RuntimeError(
                "sounddevice package is not installed. Run 'pip install -e .[voice]' to enable microphone capture."
            ) from exc
        raise
    return sd


def list_speech_providers() -> list[SpeechProvider]:
    providers = [
        SpeechProvider(
            name="text",
            kind="local",
            description="Pass transcript text directly into the voice shell.",
            requires_network=False,
        ),
        SpeechProvider(
            name="openai_audio",
            kind="remote",
            description="Transcribe an audio file through the configured OpenAI-compatible backend.",
            requires_network=True,
        ),
    ]
    if sys.platform.startswith("win"):
        providers.insert(
            1,
            SpeechProvider(
                name="windows_dictation",
                kind="local",
                description="Use built-in Windows speech recognition on the default microphone.",
                requires_network=False,
            ),
        )
    return providers


def list_windows_recognizers() -> list[RecognizerInfo]:
    if not sys.platform.startswith("win"):
        return []

    script = """
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
[System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() |
  ForEach-Object {
    [pscustomobject]@{
      culture = $_.Culture.Name
      name = $_.Name
    }
  } | ConvertTo-Json -Compress
"""
    raw = _powershell_script_output(script, timeout_s=10)
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Unexpected Windows recognizer output: {raw}") from exc

    if isinstance(payload, dict):
        payload = [payload]
    return [
        RecognizerInfo(culture=str(item.get("culture", "")).strip(), name=str(item.get("name", "")).strip())
        for item in payload
        if str(item.get("culture", "")).strip()
    ]


def get_speech_mode_config() -> SpeechModeConfig:
    if not SPEECH_MODE_PATH.exists():
        return SpeechModeConfig(language_mode="english", provider="windows_dictation", culture="auto")
    data = json.loads(SPEECH_MODE_PATH.read_text(encoding="utf-8"))
    return SpeechModeConfig(
        language_mode=_normalize_language_mode(data.get("language_mode", "english")),
        provider=_normalize_provider(data.get("provider", "windows_dictation")),
        culture=_normalize_culture(data.get("culture", "auto")),
    )


def set_speech_mode_config(
    language_mode: str | None = None,
    provider: str | None = None,
    culture: str | None = None,
) -> SpeechModeConfig:
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    current = get_speech_mode_config()
    next_cfg = SpeechModeConfig(
        language_mode=_normalize_language_mode(language_mode or current.language_mode),
        provider=_normalize_provider(provider or current.provider),
        culture=_normalize_culture(culture or current.culture),
    )
    SPEECH_MODE_PATH.write_text(json.dumps(asdict(next_cfg), indent=2), encoding="utf-8")
    return next_cfg


def speech_mode_status() -> dict[str, object]:
    cfg = get_speech_mode_config()
    recognizers = list_windows_recognizers() if sys.platform.startswith("win") else []
    recognizer_cultures = {item.culture for item in recognizers}
    resolved_culture, availability, detail = _resolve_recognition_plan(cfg, recognizer_cultures)
    return {
        "language_mode": cfg.language_mode,
        "provider": cfg.provider,
        "configured_culture": cfg.culture,
        "resolved_culture": resolved_culture,
        "availability": availability,
        "detail": detail,
        "recognizers": [asdict(item) for item in recognizers],
    }


def _normalize_language_mode(value: object) -> str:
    normalized = str(value or "english").strip().lower()
    if normalized not in {"english", "hinglish", "hindi"}:
        raise ValueError("language_mode must be one of: english, hinglish, hindi")
    return normalized


def _normalize_provider(value: object) -> str:
    normalized = str(value or "windows_dictation").strip().lower()
    if normalized not in {"windows_dictation", "openai_audio", "auto"}:
        raise ValueError("provider must be one of: windows_dictation, openai_audio, auto")
    return normalized


def _normalize_culture(value: object) -> str:
    normalized = str(value or "auto").strip()
    if not normalized:
        return "auto"
    return normalized


def transcribe_text_input(text: str) -> TranscriptionResult:
    normalized = " ".join(text.strip().split())
    return TranscriptionResult(provider="text", transcript=normalized, source="inline-text")


def transcribe_file_input(path_value: str, provider: str = "text") -> TranscriptionResult:
    source_path = Path(path_value).expanduser().resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"transcription source not found: {source_path}")

    if provider == "text":
        text = source_path.read_text(encoding="utf-8")
        return transcribe_text_input(text)

    if provider == "openai_audio":
        from openai import OpenAI

        client = OpenAI()
        with source_path.open("rb") as audio_file:
            try:
                response = client.audio.transcriptions.create(
                    model="gpt-4o-mini-transcribe",
                    file=audio_file,
                )
            except Exception as exc:
                message = _exception_chain_text(exc)
                if "CERTIFICATE_VERIFY_FAILED" in message or "certificate verify failed" in message.lower():
                    raise RuntimeError(
                        "remote audio transcription failed because the local Python trust store could not verify the TLS certificate. Fix local certificate trust or use the text provider until SSL is configured."
                    ) from exc
                raise RuntimeError(f"remote audio transcription failed: {message}") from exc
        text = getattr(response, "text", "") or ""
        return TranscriptionResult(provider="openai_audio", transcript=" ".join(text.split()), source=str(source_path))

    raise ValueError(f"Unknown speech provider: {provider}")


def _powershell_script_output(script: str, timeout_s: float) -> str:
    startupinfo = None
    creationflags = 0
    if hasattr(subprocess, "STARTUPINFO"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW

    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                encoded,
            ],
            capture_output=True,
            text=True,
            timeout=max(5, int(timeout_s) + 5),
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Windows speech recognition timed out while listening.") from exc

    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "Windows speech recognition failed.").strip()
        raise RuntimeError(message)
    return (completed.stdout or "").strip()


def transcribe_microphone_input(
    duration_s: float = 5.0,
    provider: str = "windows_dictation",
    allow_empty: bool = False,
) -> TranscriptionResult:
    speech_mode = get_speech_mode_config()
    provider = speech_mode.provider if provider == "auto" else provider
    if provider == "windows_dictation":
        recognizer_cultures = {item.culture for item in list_windows_recognizers()}
        culture_name, availability, detail = _resolve_recognition_plan(speech_mode, recognizer_cultures)
        if availability not in {"ready", "limited"}:
            raise RuntimeError(detail)
        return _transcribe_windows_dictation(duration_s, allow_empty=allow_empty, culture_name=culture_name)
    if provider == "openai_audio":
        recorded = record_microphone_clip(duration_s=duration_s)
        return transcribe_file_input(str(recorded), provider=provider)
    raise ValueError(f"Unknown speech provider: {provider}")


def _transcribe_windows_dictation(
    duration_s: float,
    *,
    allow_empty: bool = False,
    culture_name: str = "en-US",
) -> TranscriptionResult:
    if not sys.platform.startswith("win"):
        raise RuntimeError("Windows dictation is only available on Windows.")

    listen_seconds = max(2.0, float(duration_s))
    try:
        recorded = record_microphone_clip(duration_s=listen_seconds)
    except RuntimeError:
        recorded = None

    if recorded is not None:
        return _transcribe_windows_wave_file(recorded, allow_empty=allow_empty, culture_name=culture_name)

    return _transcribe_windows_default_device(listen_seconds, allow_empty=allow_empty, culture_name=culture_name)


def _transcribe_windows_default_device(
    listen_seconds: float,
    *,
    allow_empty: bool = False,
    culture_name: str = "en-US",
) -> TranscriptionResult:
    safe_culture = culture_name.replace("'", "''")
    script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$culture = [System.Globalization.CultureInfo]::GetCultureInfo('{safe_culture}')
$engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine($culture)
$grammar = New-Object System.Speech.Recognition.DictationGrammar
$engine.LoadGrammar($grammar)
$engine.SetInputToDefaultAudioDevice()
$result = $engine.Recognize([TimeSpan]::FromSeconds({listen_seconds}))
if ($null -eq $result) {{
  [Console]::Out.Write('{{"transcript":"","source":"microphone-default"}}')
}} else {{
  [Console]::Out.Write(([pscustomobject]@{{
    transcript = $result.Text
    source = 'microphone-default'
  }} | ConvertTo-Json -Compress))
}}
"""
    raw = _powershell_script_output(script, timeout_s=listen_seconds)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Unexpected Windows speech recognition output: {raw}") from exc

    transcript = " ".join(str(payload.get("transcript", "")).split())
    if not transcript:
        if allow_empty:
            return TranscriptionResult(
                provider="windows_dictation",
                transcript="",
                source=str(payload.get("source", "microphone-default")),
            )
        raise RuntimeError("No speech detected from the default microphone. Try again and speak after pressing the button.")
    return TranscriptionResult(
        provider="windows_dictation",
        transcript=transcript,
        source=str(payload.get("source", "microphone-default")),
    )


def _transcribe_windows_wave_file(
    path: Path,
    *,
    allow_empty: bool = False,
    culture_name: str = "en-US",
) -> TranscriptionResult:
    audio_path = str(path).replace("'", "''")
    safe_culture = culture_name.replace("'", "''")
    script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$culture = [System.Globalization.CultureInfo]::GetCultureInfo('{safe_culture}')
$engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine($culture)
$grammar = New-Object System.Speech.Recognition.DictationGrammar
$engine.LoadGrammar($grammar)
$engine.SetInputToWaveFile('{audio_path}')
$result = $engine.Recognize()
if ($null -eq $result) {{
  [Console]::Out.Write('{{"transcript":"","source":"wave-file"}}')
}} else {{
  [Console]::Out.Write(([pscustomobject]@{{
    transcript = $result.Text
    source = 'wave-file'
  }} | ConvertTo-Json -Compress))
}}
"""
    raw = _powershell_script_output(script, timeout_s=20)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Unexpected Windows wave transcription output: {raw}") from exc

    transcript = " ".join(str(payload.get("transcript", "")).split())
    if not transcript:
        if allow_empty:
            return TranscriptionResult(provider="windows_dictation", transcript="", source=str(path))
        raise RuntimeError("No speech detected from the configured microphone input. Check the selected mic device and try again.")
    return TranscriptionResult(provider="windows_dictation", transcript=transcript, source=str(path))


def _resolve_recognition_plan(
    cfg: SpeechModeConfig,
    recognizer_cultures: set[str],
) -> tuple[str, str, str]:
    provider = cfg.provider
    if provider == "openai_audio":
        return (cfg.culture if cfg.culture != "auto" else "remote", "ready", "Remote audio transcription selected.")

    if provider == "auto":
        provider = "windows_dictation"

    if provider != "windows_dictation":
        return (cfg.culture, "unavailable", f"Unsupported speech provider: {provider}")

    if cfg.culture != "auto":
        if cfg.culture in recognizer_cultures:
            return (cfg.culture, "ready", f"Windows recognizer {cfg.culture} is installed.")
        return (
            cfg.culture,
            "unavailable",
            f"Windows recognizer {cfg.culture} is not installed. Install that speech pack or switch provider.",
        )

    if cfg.language_mode == "english":
        for culture in ("en-IN", "en-US", "en-GB"):
            if culture in recognizer_cultures:
                return (culture, "ready", f"English mode will use Windows recognizer {culture}.")
        return ("en-US", "unavailable", "English mode requires an English Windows speech recognizer such as en-US or en-IN.")

    if cfg.language_mode == "hinglish":
        for culture in ("en-IN", "en-US"):
            if culture in recognizer_cultures:
                return (
                    culture,
                    "limited",
                    f"Hinglish mode is using {culture}. Mixed Hindi-English speech may be partial on local Windows dictation.",
                )
        return (
            "en-IN",
            "unavailable",
            "Hinglish mode needs an English recognizer such as en-IN or en-US locally, or a remote transcription provider for better mixed-language results.",
        )

    if cfg.language_mode == "hindi":
        if "hi-IN" in recognizer_cultures:
            return ("hi-IN", "ready", "Hindi mode will use the hi-IN Windows recognizer.")
        return (
            "hi-IN",
            "unavailable",
            "Hindi mode is configured, but the hi-IN Windows speech recognizer is not installed. Install the Hindi speech pack or switch to remote transcription.",
        )

    return ("en-US", "unavailable", f"Unsupported language mode: {cfg.language_mode}")


def get_microphone_config() -> MicrophoneConfig:
    if not MIC_CONFIG_PATH.exists():
        return MicrophoneConfig(device="default", sample_rate=16000, chunk_ms=250, mode="push-to-talk")
    data = json.loads(MIC_CONFIG_PATH.read_text(encoding="utf-8"))
    return MicrophoneConfig(
        device=str(data.get("device", "default")),
        sample_rate=int(data.get("sample_rate", 16000)),
        chunk_ms=int(data.get("chunk_ms", 250)),
        mode=str(data.get("mode", "push-to-talk")),
    )


def set_microphone_config(
    device: str | None = None,
    sample_rate: int | None = None,
    chunk_ms: int | None = None,
    mode: str | None = None,
) -> MicrophoneConfig:
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    current = get_microphone_config()
    next_cfg = MicrophoneConfig(
        device=device or current.device,
        sample_rate=sample_rate or current.sample_rate,
        chunk_ms=chunk_ms or current.chunk_ms,
        mode=mode or current.mode,
    )
    MIC_CONFIG_PATH.write_text(json.dumps(asdict(next_cfg), indent=2), encoding="utf-8")
    return next_cfg


def get_capture_state() -> CaptureState:
    if not CAPTURE_STATE_PATH.exists():
        return CaptureState(active=False, provider="text", mode=get_microphone_config().mode)
    data = json.loads(CAPTURE_STATE_PATH.read_text(encoding="utf-8"))
    return CaptureState(
        active=bool(data.get("active", False)),
        provider=str(data.get("provider", "text")),
        mode=str(data.get("mode", get_microphone_config().mode)),
    )


def set_capture_state(active: bool, provider: str | None = None, mode: str | None = None) -> CaptureState:
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    current = get_capture_state()
    next_state = CaptureState(
        active=active,
        provider=provider or current.provider,
        mode=mode or current.mode,
    )
    CAPTURE_STATE_PATH.write_text(json.dumps(asdict(next_state), indent=2), encoding="utf-8")
    return next_state


def list_input_devices() -> list[InputDevice]:
    sd = _load_sounddevice()
    devices = sd.query_devices()
    items: list[InputDevice] = []
    for idx, device in enumerate(devices):
        max_input_channels = int(device.get("max_input_channels", 0))
        if max_input_channels <= 0:
            continue
        items.append(
            InputDevice(
                index=idx,
                name=str(device.get("name", f"device-{idx}")),
                max_input_channels=max_input_channels,
                default_sample_rate=int(float(device.get("default_samplerate", 16000))),
            )
        )
    return items


def record_microphone_clip(duration_s: float, output_path: str | None = None) -> Path:
    sd = _load_sounddevice()
    config = get_microphone_config()
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

    frames = int(duration_s * config.sample_rate)
    device = None if config.device == "default" else config.device
    try:
        recording = sd.rec(
            frames,
            samplerate=config.sample_rate,
            channels=1,
            dtype="int16",
            device=device,
        )
    except ImportError as exc:
        raise RuntimeError(
            "numpy is required for live microphone recording. Run 'pip install -e .[voice]' again to install the full voice extras."
        ) from exc
    sd.wait()

    if output_path:
        target = Path(output_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
    else:
        target = RECORDINGS_DIR / f"capture_{config.sample_rate}hz_{frames}f.wav"

    with wave.open(str(target), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(config.sample_rate)
        wav_file.writeframes(recording.tobytes())

    return target