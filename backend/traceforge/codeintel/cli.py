"""Self-check CLI: `python -m traceforge.codeintel <repo> [--bench] [--map] [--distance A B]`."""

import argparse
import json
import shutil
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

from .codemap import approx_tokens, code_map
from .graph import DEFAULT_CACHE, build_graph
from .queries import distance, stats


def peak_rss_mb() -> float | None:
    """Peak working set of this process (Windows ctypes, else resource)."""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                    (n, ctypes.c_size_t)
                    for n in (
                        "PeakWorkingSetSize",
                        "WorkingSetSize",
                        "QuotaPeakPagedPoolUsage",
                        "QuotaPagedPoolUsage",
                        "QuotaPeakNonPagedPoolUsage",
                        "QuotaNonPagedPoolUsage",
                        "PagefileUsage",
                        "PeakPagefileUsage",
                    )
                ]

            k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
            k32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(PMC),
                wintypes.DWORD,
            ]
            pmc = PMC()
            pmc.cb = ctypes.sizeof(pmc)
            psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
            return pmc.PeakWorkingSetSize / 2**20
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:  # noqa: BLE001 - best-effort measurement
        return None


def _timed(repo, sha, cache_dir):
    t = time.perf_counter()
    g = build_graph(repo, sha, cache_dir=cache_dir)
    return g, time.perf_counter() - t


def bench(repo: Path, sha: str | None) -> dict:
    out: dict = {}
    tmp = Path(tempfile.mkdtemp(prefix="graphbench_"))
    try:
        _g, out["cold_no_cache_s"] = _timed(repo, sha, None)
        tracemalloc.start()
        build_graph(repo, sha, cache_dir=None)
        out["tracemalloc_peak_mb"] = round(tracemalloc.get_traced_memory()[1] / 2**20, 1)
        tracemalloc.stop()
        g, out["cold_write_cache_s"] = _timed(repo, sha, tmp / "c")
        out["files"] = g.stats["python_files"]
        g, out["warm_cache_s"] = _timed(repo, sha, tmp / "c")
        out["warm_reparsed"] = g.stats["reparsed"]
        copy = tmp / "copy"
        shutil.copytree(
            repo,
            copy,
            ignore=shutil.ignore_patterns(
                ".venv", "venv", "__pycache__", ".git", ".cache", "node_modules"
            ),
        )
        _g, _ = _timed(copy, sha, tmp / "c2")
        victim = sorted(copy.rglob("*.py"))[len(list(copy.rglob("*.py"))) // 2]
        victim.write_text(
            victim.read_text(encoding="utf-8") + "\n\ndef _bench_added():\n    pass\n",
            encoding="utf-8",
        )
        g, out["incremental_1_file_s"] = _timed(copy, sha, tmp / "c2")
        out["incremental_reparsed"] = g.stats["reparsed"]
        out["incremental_file"] = victim.relative_to(copy).as_posix()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    out["peak_rss_mb_whole_process"] = peak_rss_mb()
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="traceforge.codeintel")
    ap.add_argument("repo")
    ap.add_argument("--sha")
    ap.add_argument("--cache-dir", default=str(DEFAULT_CACHE))
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--bench", action="store_true")
    ap.add_argument("--map", action="store_true", help="print the code map and its token estimate")
    ap.add_argument("--distance", nargs=2, metavar=("A", "B"))
    a = ap.parse_args(argv)
    repo = Path(a.repo)
    g, secs = _timed(repo, a.sha, None if a.no_cache else Path(a.cache_dir))
    s = stats(g)
    print(f"repo={g.repo} base_sha={g.base_sha} content_hash={g.content_hash[:12]}")
    print(
        json.dumps(
            {k: v for k, v in s.items() if not k.endswith("_s") and "seconds" not in k}, indent=2
        )
    )
    print(
        f"build: {secs:.3f}s (parse {s['parse_seconds']:.3f}s, "
        f"assemble {s['assemble_seconds']:.3f}s)"
    )
    if a.distance:
        print("distance:", distance(g, *a.distance))
    if a.map:
        m = code_map(g)
        print(m)
        print(f"-- code map: {len(m)} chars, ~{approx_tokens(m)} tokens (chars/4 estimate)")
    if a.bench:
        print(json.dumps(bench(repo, a.sha), indent=2))


if __name__ == "__main__":
    main()
