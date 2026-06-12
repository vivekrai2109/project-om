from __future__ import annotations


SAFE_INTERNET_LEARNING_DOMAINS: tuple[str, ...] = (
    "finance",
    "legal",
    "cloud",
    "networking",
    "coding_languages",
    "software_architecture",
    "security_defensive",
    "data_engineering",
    "systems_design",
)

DISALLOWED_LEARNING_CATEGORIES: tuple[str, ...] = (
    "harmful_illegal_how_to",
    "malware_offense",
    "fraud_or_evasion",
    "privacy_abuse",
    "unsafe_bio_or_chemical",
)

DEFAULT_COMPUTE_MODE = "balanced"
COMPUTE_MODES: tuple[str, ...] = ("lean", "balanced", "performance")

DOMAIN_ALIASES: dict[str, str] = {
    "finance": "finance",
    "legal": "legal",
    "cloud": "cloud",
    "networking": "networking",
    "coding": "coding_languages",
    "coding languages": "coding_languages",
    "software architecture": "software_architecture",
    "architecture": "software_architecture",
    "defensive security": "security_defensive",
    "security": "security_defensive",
    "data engineering": "data_engineering",
    "systems design": "systems_design",
}


def default_internet_learning_domains() -> list[str]:
    return list(SAFE_INTERNET_LEARNING_DOMAINS)


def normalize_compute_mode(value: object) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in COMPUTE_MODES else DEFAULT_COMPUTE_MODE


def internet_learning_scope_summary(domains: list[str]) -> str:
    visible = ", ".join(domains[:6])
    suffix = "" if len(domains) <= 6 else ", ..."
    return visible + suffix if visible else "none"


def normalize_internet_learning_domains(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        key = str(value or "").strip().lower().replace("_", " ")
        mapped = DOMAIN_ALIASES.get(key, str(value or "").strip().lower().replace(" ", "_"))
        if mapped in SAFE_INTERNET_LEARNING_DOMAINS and mapped not in normalized:
            normalized.append(mapped)
    return normalized


def parse_compute_mode_command(text: str) -> str | None:
    normalized = " ".join(str(text or "").strip().lower().split())
    for mode in COMPUTE_MODES:
        if normalized in {
            f"set compute mode to {mode}",
            f"compute mode {mode}",
            f"use {mode} compute mode",
        }:
            return mode
    return None


def parse_internet_learning_domain_command(text: str) -> tuple[str, list[str]] | None:
    normalized = " ".join(str(text or "").strip().lower().split())
    prefixes = {
        "set internet learning domains to ": "set",
        "allow internet learning for ": "set",
        "add internet learning domain ": "add",
        "add internet learning domains ": "add",
        "remove internet learning domain ": "remove",
        "remove internet learning domains ": "remove",
    }
    for prefix, operation in prefixes.items():
        if normalized.startswith(prefix):
            raw = normalized[len(prefix) :]
            parts = [segment.strip() for segment in raw.replace(" and ", ",").split(",")]
            domains = normalize_internet_learning_domains(parts)
            return operation, domains
    return None