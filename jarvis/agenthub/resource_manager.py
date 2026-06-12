from __future__ import annotations

from dataclasses import dataclass, field
import ctypes
import os
import shutil
import sys
from typing import Any

from .config import load_config


@dataclass(slots=True)
class ResourceSnapshot:
    cpu_percent: float | None
    ram_percent: float | None
    active_backend: str
    omnira_online: bool
    ollama_online: bool
    active_model: str
    model_latency_ms: float | None
    active_tasks: int
    pending_approvals: int
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ResourceManager:
    def __init__(self) -> None:
        self._last_cpu_percent: float | None = None

    def collect(
        self,
        *,
        omnira_online: bool,
        active_model: str,
        active_tasks: int,
        pending_approvals: int,
        model_latency_ms: float | None = None,
    ) -> ResourceSnapshot:
        cfg = load_config()
        warnings: list[str] = []
        cpu_percent = self._cpu_percent()
        ram_percent = self._ram_percent()
        if cpu_percent is None:
            warnings.append("cpu_metric_unavailable")
        if ram_percent is None:
            warnings.append("ram_metric_unavailable")
        if not omnira_online:
            warnings.append("omnira_offline")
        if ram_percent is not None and ram_percent >= 85.0:
            warnings.append("high_memory_usage")
        if active_tasks >= 4:
            warnings.append("task_backlog")
        return ResourceSnapshot(
            cpu_percent=cpu_percent,
            ram_percent=ram_percent,
            active_backend=cfg.backend,
            omnira_online=bool(omnira_online),
            ollama_online=bool(shutil.which("ollama")),
            active_model=str(active_model or cfg.model),
            model_latency_ms=model_latency_ms,
            active_tasks=max(0, int(active_tasks)),
            pending_approvals=max(0, int(pending_approvals)),
            warnings=warnings,
            metadata={"platform": sys.platform},
        )

    def routing_hints(self, snapshot: ResourceSnapshot) -> list[str]:
        hints: list[str] = []
        if not snapshot.omnira_online:
            hints.append("stay_in_local_mode")
        if snapshot.ram_percent is not None and snapshot.ram_percent >= 85.0:
            hints.append("prefer_smaller_model")
        if snapshot.active_tasks >= 3:
            hints.append("prefer_background_task")
        if not snapshot.ollama_online:
            hints.append("local_model_runtime_unavailable")
        return hints

    def _cpu_percent(self) -> float | None:
        try:
            import psutil  # type: ignore

            self._last_cpu_percent = float(psutil.cpu_percent(interval=0.0))
            return self._last_cpu_percent
        except Exception:
            return None

    def _ram_percent(self) -> float | None:
        try:
            import psutil  # type: ignore

            return float(psutil.virtual_memory().percent)
        except Exception:
            pass

        if not sys.platform.startswith("win"):
            return None

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stats = MEMORYSTATUSEX()
        stats.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stats)):
            return None
        return float(stats.dwMemoryLoad)