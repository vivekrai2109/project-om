from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .config import data_dir


OWNER_PROFILE_PATH = data_dir() / "voice" / "owner_profile.json"


@dataclass
class OwnerProfile:
    owner_name: str = ""
    response_style: str = "concise"
    preferences: list[str] = field(default_factory=list)
    aliases: list[dict[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    updated_at: str = ""


def load_owner_profile() -> OwnerProfile:
    if not OWNER_PROFILE_PATH.exists():
        return OwnerProfile()
    try:
        data = json.loads(OWNER_PROFILE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return OwnerProfile()
    return OwnerProfile(
        owner_name=str(data.get("owner_name", "")).strip(),
        response_style=_normalize_response_style(data.get("response_style", "concise")),
        preferences=[str(item).strip() for item in data.get("preferences", []) if str(item).strip()],
        aliases=[
            {"spoken": str(item.get("spoken", "")).strip(), "meaning": str(item.get("meaning", "")).strip()}
            for item in data.get("aliases", [])
            if str(item.get("spoken", "")).strip() and str(item.get("meaning", "")).strip()
        ],
        notes=[str(item).strip() for item in data.get("notes", []) if str(item).strip()],
        updated_at=str(data.get("updated_at", "")).strip(),
    )


def save_owner_profile(profile: OwnerProfile) -> None:
    OWNER_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    profile.updated_at = datetime.now(timezone.utc).isoformat()
    OWNER_PROFILE_PATH.write_text(json.dumps(asdict(profile), indent=2), encoding="utf-8")


def bind_owner_name(name: str) -> OwnerProfile:
    profile = load_owner_profile()
    normalized = " ".join(name.strip().split())
    if normalized:
        profile.owner_name = normalized
        save_owner_profile(profile)
    return profile


def learn_from_message(message: str) -> tuple[OwnerProfile, list[str]]:
    profile = load_owner_profile()
    normalized = " ".join(message.strip().split())
    lowered = normalized.lower()
    learned: list[str] = []

    if not normalized:
        return profile, learned

    preference_match = re.search(r"\bi prefer\s+(.+?)(?:[.!?]|$)", normalized, flags=re.IGNORECASE)
    if preference_match:
        preference = preference_match.group(1).strip(" .,!?")[:140]
        if preference and preference.lower() not in {item.lower() for item in profile.preferences}:
            profile.preferences.append(preference)
            learned.append(f"preference:{preference}")

    alias_match = re.search(r"\bwhen i say\s+(.+?)\s*,?\s*(?:i mean|that means)\s+(.+?)(?:[.!?]|$)", normalized, flags=re.IGNORECASE)
    if alias_match:
        spoken = alias_match.group(1).strip(" .,!?")[:80]
        meaning = alias_match.group(2).strip(" .,!?")[:120]
        if spoken and meaning:
            existing = {(item["spoken"].lower(), item["meaning"].lower()) for item in profile.aliases}
            if (spoken.lower(), meaning.lower()) not in existing:
                profile.aliases.append({"spoken": spoken, "meaning": meaning})
                learned.append(f"alias:{spoken}")

    if any(token in lowered for token in ("be concise", "be brief", "reply briefly", "respond briefly", "keep it short")):
        if profile.response_style != "concise":
            profile.response_style = "concise"
            learned.append("response_style:concise")

    if any(token in lowered for token in ("be detailed", "be more detailed", "go deeper", "explain more", "full detail")):
        if profile.response_style != "detailed":
            profile.response_style = "detailed"
            learned.append("response_style:detailed")

    if any(token in lowered for token in ("my accent", "my pronunciation", "learn how i speak", "adapt to my voice")):
        note = "Owner wants speech adaptation and accent-aware understanding."
        if note not in profile.notes:
            profile.notes.append(note)
            learned.append("note:speech_adaptation")

    if learned:
        save_owner_profile(profile)
    return profile, learned


def summarize_owner_profile(profile: OwnerProfile | None = None) -> str:
    current = profile or load_owner_profile()
    parts: list[str] = []
    if current.owner_name:
        parts.append(f"Owner name: {current.owner_name}.")
    parts.append(f"Preferred response style: {current.response_style}.")
    if current.preferences:
        parts.append("Known owner preferences: " + "; ".join(current.preferences[:4]) + ".")
    if current.aliases:
        alias_text = "; ".join(f"'{item['spoken']}' means '{item['meaning']}'" for item in current.aliases[:4])
        parts.append("Known phrase mappings: " + alias_text + ".")
    if current.notes:
        parts.append("Adaptive notes: " + "; ".join(current.notes[:3]) + ".")
    return " ".join(parts).strip()


def set_response_style(style: str) -> OwnerProfile:
    profile = load_owner_profile()
    profile.response_style = _normalize_response_style(style)
    save_owner_profile(profile)
    return profile


def replace_preferences(raw_text: str) -> OwnerProfile:
    profile = load_owner_profile()
    profile.preferences = _parse_lines(raw_text, limit=12, item_limit=140)
    save_owner_profile(profile)
    return profile


def replace_notes(raw_text: str) -> OwnerProfile:
    profile = load_owner_profile()
    profile.notes = _parse_lines(raw_text, limit=12, item_limit=180)
    save_owner_profile(profile)
    return profile


def replace_aliases(raw_text: str) -> OwnerProfile:
    profile = load_owner_profile()
    profile.aliases = _parse_alias_lines(raw_text)
    save_owner_profile(profile)
    return profile


def preferences_text(profile: OwnerProfile | None = None) -> str:
    current = profile or load_owner_profile()
    return "\n".join(current.preferences)


def notes_text(profile: OwnerProfile | None = None) -> str:
    current = profile or load_owner_profile()
    return "\n".join(current.notes)


def aliases_text(profile: OwnerProfile | None = None) -> str:
    current = profile or load_owner_profile()
    return "\n".join(f"{item['spoken']} = {item['meaning']}" for item in current.aliases)


def _normalize_response_style(value: object) -> str:
    normalized = str(value or "concise").strip().lower()
    if normalized not in {"concise", "detailed"}:
        return "concise"
    return normalized


def _parse_lines(raw_text: str, *, limit: int, item_limit: int) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for line in str(raw_text).splitlines():
        cleaned = " ".join(line.strip().split())[:item_limit].strip(" .,!?")
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        items.append(cleaned)
        seen.add(lowered)
        if len(items) >= limit:
            break
    return items


def _parse_alias_lines(raw_text: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for line in str(raw_text).splitlines():
        cleaned = " ".join(line.strip().split())
        if not cleaned:
            continue
        if "=" in cleaned:
            spoken, meaning = cleaned.split("=", 1)
        elif ":" in cleaned:
            spoken, meaning = cleaned.split(":", 1)
        else:
            continue
        spoken_value = spoken.strip(" .,!?")[:80]
        meaning_value = meaning.strip(" .,!?")[:120]
        if not spoken_value or not meaning_value:
            continue
        key = (spoken_value.lower(), meaning_value.lower())
        if key in seen:
            continue
        items.append({"spoken": spoken_value, "meaning": meaning_value})
        seen.add(key)
        if len(items) >= 12:
            break
    return items