"""Collect hardware, GPU/VRAM, runtime version, and git state for manifests."""

from __future__ import annotations

import platform
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil


def _run_short(cmd: list[str], timeout: float = 5.0, require_ok: bool = False) -> str | None:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if require_ok and proc.returncode != 0:
            return None
        out = (proc.stdout or proc.stderr or "").strip()
        return out if out else None
    except Exception:
        return None


def get_gpu_info() -> dict[str, Any]:
    """Query NVIDIA GPU specs & current VRAM usage via nvidia-ml-py (pynvml)."""
    try:
        import pynvml

        pynvml.nvmlInit()
        try:
            count = pynvml.nvmlDeviceGetCount()
            driver = pynvml.nvmlSystemGetDriverVersion()
            if isinstance(driver, bytes):
                driver = driver.decode("utf-8", errors="replace")
            gpus = []
            for idx in range(count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8", errors="replace")
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                gpus.append(
                    {
                        "index": idx,
                        "name": name,
                        "vram_total_mb": round(mem.total / (1024 * 1024), 1),
                        "vram_used_mb": round(mem.used / (1024 * 1024), 1),
                        "vram_free_mb": round(mem.free / (1024 * 1024), 1),
                    }
                )
            return {"driver_version": driver, "gpus": gpus}
        finally:
            pynvml.nvmlShutdown()
    except Exception as exc:
        return {"driver_version": None, "gpus": [], "error": str(exc)}


def current_vram_used_mb(device_index: int = 0) -> float | None:
    """Return current VRAM usage in MiB for the given NVIDIA GPU, or None."""
    try:
        import pynvml

        pynvml.nvmlInit()
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(device_index)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            return round(mem.used / (1024 * 1024), 1)
        finally:
            pynvml.nvmlShutdown()
    except Exception:
        return None


def detect_llamacpp_binary() -> tuple[str | None, list[str]]:
    """Detect available llama.cpp server binary (llama-server or unified llama serve)."""
    if path := shutil.which("llama-server"):
        return path, [path]
    if path := shutil.which("llama"):
        return path, [path, "serve"]
    return None, []


def get_runtime_versions() -> dict[str, Any]:
    versions: dict[str, Any] = {}
    llama_bin, _ = detect_llamacpp_binary()
    versions["llamacpp_bin"] = llama_bin
    if llama_bin:
        versions["llamacpp_version"] = _run_short([llama_bin, "--version"])
    else:
        versions["llamacpp_version"] = None

    ollama_bin = shutil.which("ollama")
    versions["ollama_bin"] = ollama_bin
    versions["ollama_version"] = _run_short([ollama_bin, "--version"]) if ollama_bin else None
    return versions


def get_git_info(cwd: Path | None = None) -> dict[str, Any]:
    base = [str(cwd)] if cwd else []
    git_cmd = ["git", "-C", *base] if base else ["git"]
    commit = _run_short([*git_cmd, "rev-parse", "HEAD"], require_ok=True)
    status = _run_short([*git_cmd, "status", "--porcelain"], require_ok=True) if commit else None
    return {
        "commit": commit,
        "dirty": bool(status) if commit else None,
    }


def collect_sysinfo(cwd: Path | None = None) -> dict[str, Any]:
    vm = psutil.virtual_memory()
    return {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "os": platform.platform(),
        "python": platform.python_version(),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "ram_total_gb": round(vm.total / (1024**3), 2),
        "gpu": get_gpu_info(),
        "runtimes": get_runtime_versions(),
        "git": get_git_info(cwd),
    }
