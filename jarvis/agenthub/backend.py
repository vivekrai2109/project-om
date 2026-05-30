from __future__ import annotations

from .backend_client import check_backend_connection
from .config import load_config


def check_backend() -> tuple[bool, str]:
    cfg = load_config()
    return check_backend_connection(cfg)
