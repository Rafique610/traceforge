"""Hardware sampler for local-model runs (P5-S04): GPU memory/utilisation and system RAM.

Stdlib only. `nvidia-smi` is read through a subprocess; on machines without it GPU fields are None.
Use as a context manager around a run; `summary()` gives peaks and the sample count. Nothing here
touches a provider or the pipeline.
"""

from __future__ import annotations

import ctypes
import subprocess
import threading
import time
from dataclasses import dataclass, field

_GPU_QUERY = [
    "nvidia-smi",
    "--query-gpu=memory.used,utilization.gpu",
    "--format=csv,noheader,nounits",
]


@dataclass
class Sample:
    t: float
    gpu_mem_mib: int | None
    gpu_util_pct: int | None
    ram_used_mib: int | None


def read_gpu() -> tuple[int | None, int | None]:
    try:
        out = subprocess.run(_GPU_QUERY, capture_output=True, text=True, timeout=5, check=True)
        mem, util = (int(x.strip()) for x in out.stdout.splitlines()[0].split(","))
        return mem, util
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None, None


class _MemStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]  # fmt: skip


def read_ram_used_mib() -> int | None:
    """Used physical RAM in MiB (Windows API, or /proc/meminfo); None if unavailable."""
    try:
        if hasattr(ctypes, "windll"):
            m = _MemStatus()
            m.dwLength = ctypes.sizeof(m)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return int((m.ullTotalPhys - m.ullAvailPhys) // 2**20)
        info = dict(
            line.split(":", 1)
            for line in open("/proc/meminfo", encoding="utf-8").read().splitlines()
        )
        kib = lambda k: int(info[k].split()[0])  # noqa: E731
        return (kib("MemTotal") - kib("MemAvailable")) // 1024
    except (OSError, KeyError, ValueError, AttributeError):
        return None


@dataclass
class HwMonitor:
    interval_s: float = 2.0
    samples: list[Sample] = field(default_factory=list)
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)

    def sample(self) -> Sample:
        mem, util = read_gpu()
        s = Sample(time.time(), mem, util, read_ram_used_mib())
        self.samples.append(s)
        return s

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.sample()
            self._stop.wait(self.interval_s)

    def __enter__(self) -> HwMonitor:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=self.interval_s + 5)
        self.sample()

    def summary(self) -> dict:
        def peak(vals):
            vals = [v for v in vals if v is not None]
            return max(vals) if vals else None

        return {
            "samples": len(self.samples),
            "interval_s": self.interval_s,
            "gpu_mem_peak_mib": peak(s.gpu_mem_mib for s in self.samples),
            "gpu_util_peak_pct": peak(s.gpu_util_pct for s in self.samples),
            "ram_used_peak_mib": peak(s.ram_used_mib for s in self.samples),
        }
