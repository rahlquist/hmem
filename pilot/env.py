"""Environment and resource capture for the hmem pilot.

psutil is used when installed; every measurement has a standard-library
fallback (/proc parsing, resource.getrusage, shutil.disk_usage) so the harness
runs on a clean machine with zero third-party dependencies. System-wide
counters (stdlib fallback) are documented limitations.
"""
import datetime
import math
import os
import platform
import re
import shutil

try:
    import psutil as _psutil
except Exception:  # pragma: no cover - fallback path exercised on clean machines
    _psutil = None


def capture_environment():
    """Declared environment snapshot, written into the run manifest."""
    return {
        "os": platform.platform(),
        "python_version": platform.python_version(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count() or 0,
        "captured_iso": _now_iso(),
    }


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def percentiles(samples, ps=(50, 95)):
    """Nearest-rank percentiles. Returns {"p50": float|None, "p95": float|None}."""
    out = {}
    if not samples:
        return {f"p{p}": None for p in ps}
    ordered = sorted(samples)
    for p in ps:
        idx = max(0, min(len(ordered) - 1, int(math.ceil(p / 100.0 * len(ordered))) - 1))
        out[f"p{p}"] = float(ordered[idx])
    return out


def estimate_tokens(text):
    """Deterministic whitespace-token estimate (not a provider tokenizer)."""
    return len(re.findall(r"\S+", text or ""))


def _proc_cpu_percent():
    """CPU busy ratio over a ~100ms window via /proc/stat (stdlib fallback)."""
    try:
        with open("/proc/stat", "r", encoding="utf-8") as fh:
            first = [int(x) for x in fh.readline().split()[1:]]
        import time
        time.sleep(0.1)
        with open("/proc/stat", "r", encoding="utf-8") as fh:
            second = [int(x) for x in fh.readline().split()[1:]]
        idle1, idle2 = first[3], second[3]
        total1, total2 = sum(first), sum(second)
        delta_total = total2 - total1
        if delta_total <= 0:
            return None
        delta_idle = idle2 - idle1
        return round(100.0 * (delta_total - delta_idle) / delta_total, 2)
    except Exception:
        return None


def _proc_net_tx_bytes():
    """Sum of transmitted bytes across interfaces from /proc/net/dev (stdlib)."""
    try:
        total = 0
        with open("/proc/net/dev", "r", encoding="utf-8") as fh:
            for line in fh:
                if ":" not in line:
                    continue
                fields = line.split(":")
                parts = fields[1].split()
                if len(parts) >= 9:
                    total += int(parts[8])  # transmit bytes
        return total
    except Exception:
        return None


def resource_snapshot(workdir=None):
    """One snapshot of CPU%, peak RSS, free disk (MB) and cumulative net egress."""
    cpu = None
    if _psutil is not None:
        try:
            cpu = _psutil.cpu_percent(interval=None)
        except Exception:
            cpu = None
    if cpu is None:
        cpu = _proc_cpu_percent()

    peak = None
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0  # KB -> MB
    except Exception:
        peak = None

    disk = None
    try:
        disk = shutil.disk_usage(workdir or os.getcwd()).free / (1024.0 * 1024.0)
    except Exception:
        disk = None

    net = None
    if _psutil is not None:
        try:
            net = _psutil.net_io_counters().bytes_sent
        except Exception:
            net = None
    if net is None:
        net = _proc_net_tx_bytes()

    return {
        "cpu_percent": cpu,
        "peak_ram_mb": peak,
        "disk_free_mb": disk,
        "network_egress_bytes": net,
    }


def measure_resources(before, after, workdir=None):
    """Deltas between two snapshots; None when a source value is unavailable."""
    disk_growth = None
    if before.get("disk_free_mb") is not None and after.get("disk_free_mb") is not None:
        disk_growth = round(before["disk_free_mb"] - after["disk_free_mb"], 3)
    net_delta = None
    if (before.get("network_egress_bytes") is not None
            and after.get("network_egress_bytes") is not None):
        net_delta = max(0, after["network_egress_bytes"] - before["network_egress_bytes"])
    return {
        "cpu_percent": after.get("cpu_percent"),
        "peak_ram_mb": after.get("peak_ram_mb"),
        "disk_growth_mb": disk_growth,
        "network_egress_bytes": net_delta,
    }
