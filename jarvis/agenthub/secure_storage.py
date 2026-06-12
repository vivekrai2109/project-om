from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path
import json
import os
from typing import Any


CRYPTPROTECT_UI_FORBIDDEN = 0x01


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def storage_encryption_status() -> tuple[bool, str]:
    if os.name == "nt":
        return True, "windows_dpapi"
    return False, "not_configured"


def encryption_enabled() -> bool:
    enabled, _ = storage_encryption_status()
    return enabled


def encrypted_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".enc") if path.suffix else Path(str(path) + ".enc")


def _windows_encrypt(data: bytes) -> bytes:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(DATA_BLOB),
        wintypes.LPCWSTR,
        ctypes.POINTER(DATA_BLOB),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL

    in_buffer = ctypes.create_string_buffer(data)
    in_blob = DATA_BLOB(len(data), ctypes.cast(in_buffer, ctypes.POINTER(ctypes.c_byte)))
    out_blob = DATA_BLOB()
    if not crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "Jarvis Local Data",
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    ):
        raise OSError(ctypes.get_last_error(), "CryptProtectData failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _windows_decrypt(data: bytes) -> bytes:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DATA_BLOB),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(DATA_BLOB),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL

    in_buffer = ctypes.create_string_buffer(data)
    in_blob = DATA_BLOB(len(data), ctypes.cast(in_buffer, ctypes.POINTER(ctypes.c_byte)))
    out_blob = DATA_BLOB()
    description = wintypes.LPWSTR()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        ctypes.byref(description),
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    ):
        raise OSError(ctypes.get_last_error(), "CryptUnprotectData failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)
        if description:
            kernel32.LocalFree(description)


def _encrypt_bytes(data: bytes) -> bytes:
    if not encryption_enabled():
        return data
    return _windows_encrypt(data)


def _decrypt_bytes(data: bytes) -> bytes:
    if not encryption_enabled():
        return data
    return _windows_decrypt(data)


def _resolve_read_path(path: Path) -> tuple[Path | None, bool]:
    if str(path).endswith(".enc"):
        return (path, True) if path.exists() else (None, True)
    secure = encrypted_path(path)
    if secure.exists():
        return secure, True
    if path.exists():
        return path, False
    return None, False


def write_text_file(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if encryption_enabled():
        target = encrypted_path(path)
        target.write_bytes(_encrypt_bytes(text.encode("utf-8")))
        if path.exists():
            path.unlink()
        return target
    path.write_text(text, encoding="utf-8")
    return path


def read_text_file(path: Path, default: str = "") -> str:
    target, is_encrypted = _resolve_read_path(path)
    if target is None:
        return default
    if is_encrypted:
        return _decrypt_bytes(target.read_bytes()).decode("utf-8")
    return target.read_text(encoding="utf-8")


def write_json_file(path: Path, payload: dict[str, Any]) -> Path:
    return write_text_file(path, json.dumps(payload, indent=2, ensure_ascii=True))


def read_json_file(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    text = read_text_file(path, default="")
    if not text:
        return dict(default or {})
    return json.loads(text)


def iter_json_like_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    plain = {path for path in root.rglob("*.json") if path.is_file() and not str(path).endswith(".json.enc")}
    encrypted = {path for path in root.rglob("*.json.enc") if path.is_file()}
    return sorted(plain | encrypted)