"""P0-S06 Part B: model probe (read limit, write limit, format comparison, rates/latency).

Run from backend/ with the project venv:
    python ../spikes/model_probe/probe.py --exp all
    python ../spikes/model_probe/probe.py --exp read --provider openrouter --model "<id>:free" --ctx 32768

All model calls go through traceforge.agent.gateway.chat (cache, call log, :free guard).
Calls are strictly sequential. Spike code: never imported by backend/.
"""

from __future__ import annotations

import os
import argparse
import ast
import ctypes
import json
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "backend"))

import codegen  # noqa: E402
from traceforge.agent import gateway  # noqa: E402
from traceforge.config import Settings  # noqa: E402
from traceforge.repair import edits, policy  # noqa: E402

RESULTS = HERE / os.environ.get("PROBE_RESULTS", "results")
CALL_TIMEOUT_S = 1800.0
MIN_FREE_RAM_MB = 150

SR_SPEC = (
    "Reply with edit blocks ONLY, no explanations. Format, one block per change:\n"
    "<<<<<<< SEARCH path/to/file.py\n<exact lines copied from the file>\n=======\n"
    "<replacement lines>\n>>>>>>> REPLACE\n"
    "The SEARCH text must match the file exactly and appear once. Edit source files only, "
    "never test files."
)
DIFF_SPEC = (
    "Reply with a unified diff ONLY, no explanations. Use `--- a/path` / `+++ b/path` headers and "
    "`@@ -l,n +l,n @@` hunk headers with correct line counts, 3 lines of context. "
    "Edit source files only, never test files."
)


# ---------------------------------------------------------------- machine monitoring
def free_ram_mb() -> float:
    class MS(ctypes.Structure):
        _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (n, ctypes.c_ulonglong) for n in ("tp", "ap", "tpf", "apf", "tv", "av", "ae")
        ]

    m = MS()
    m.l = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ap / 2**20


def gpu_used_mib() -> int | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout  # fmt: skip
        return int(out.strip().splitlines()[0])
    except Exception:
        return None


class GpuSampler:
    """Samples nvidia-smi every 2 s in a thread; keeps the peak and baseline."""

    def __init__(self) -> None:
        self.samples: list[int] = []
        self.baseline = gpu_used_mib()
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.wait(2.0):
            v = gpu_used_mib()
            if v is not None:
                self.samples.append(v)

    def __enter__(self) -> GpuSampler:
        self._t.start()
        return self

    def __exit__(self, *a) -> None:
        self._stop.set()
        self._t.join(5)

    def summary(self) -> dict:
        return {
            "vram_baseline_mib": self.baseline,
            "vram_peak_mib": max(self.samples) if self.samples else self.baseline,
            "vram_samples": len(self.samples),
        }


def hardware(args) -> dict:
    hw: dict = {"os": sys.platform, "free_ram_mb_at_start": round(free_ram_mb())}
    try:
        hw["gpu"] = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()  # fmt: skip
    except Exception:
        hw["gpu"] = None
    if args.provider == "ollama":
        try:
            base = args.ollama_url.replace("/v1", "")
            ps = json.load(urllib.request.urlopen(base + "/api/ps", timeout=10))["models"]
            hw["ollama_loaded"] = [
                {k: m.get(k) for k in ("name", "size", "size_vram", "context_length")} for m in ps
            ]
        except Exception as e:
            hw["ollama_loaded"] = f"unavailable: {type(e).__name__}"
    return hw


# ---------------------------------------------------------------- gateway wrapper
class Ctx:
    def __init__(self, args) -> None:
        self.args = args
        self.settings = Settings(
            llm_provider=args.provider,
            llm_model=args.model,
            llm_cache_dir=HERE / ".cache" / "llm",
            llm_call_log=RESULTS / "llm_calls.jsonl",
            llm_max_rps=1.0,
            ollama_base_url=args.ollama_url,
        )
        gateway.check_allowed(self.settings)  # fail fast on non-:free openrouter ids
        self.client = gateway.make_client(self.settings).with_options(timeout=CALL_TIMEOUT_S)
        self.stop_reason: str | None = None

    def ask(self, system: str, user: str, max_tokens: int) -> dict:
        """One sequential gateway call. Never raises; returns a record with error on failure."""
        if free_ram_mb() < MIN_FREE_RAM_MB:
            self.stop_reason = f"free RAM below {MIN_FREE_RAM_MB} MB"
            return {"error": self.stop_reason, "aborted": True}
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        t0 = time.monotonic()
        try:
            r = gateway.chat(
                msgs, settings=self.settings, client=self.client, max_tokens=max_tokens,
                temperature=0.0, use_cache=not self.args.no_cache,
            )  # fmt: skip
        except gateway.GatewayError as e:
            return {"error": str(e), "wall_ms": (time.monotonic() - t0) * 1000}
        return {
            "reply": r.content or "",
            "tokens_in": r.tokens_in,
            "tokens_out": r.tokens_out,
            "latency_ms": round(r.latency_ms, 1),
            "cache_hit": r.cache_hit,
            "finish_reason": r.finish_reason,
            "truncated_output": r.finish_reason == "length",
            "prompt_chars": len(system) + len(user),
        }


def save(name: str, data: dict) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{name}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def numbered(files: dict[str, str]) -> str:
    out = []
    for p, t in files.items():
        out.append(f"=== FILE: {p} ===")
        out += [f"{i:4d}| {ln}" for i, ln in enumerate(t.splitlines(), 1)]
    return "\n".join(out)


def plain(files: dict[str, str]) -> str:
    return "\n\n".join(f"=== FILE: {p} ===\n{t}" for p, t in files.items())


# ---------------------------------------------------------------- quality helpers
def ruff_codes(text: str) -> Counter:
    exe = shutil.which("ruff") or str(Path(sys.executable).parent / "ruff.exe")
    p = subprocess.run(
        [exe, "check", "--isolated", "--select", "E,F,W", "--line-length", "100",
         "--output-format", "json", "--stdin-filename", "x.py", "-"],
        input=text, capture_output=True, text=True, timeout=60,
    )  # fmt: skip
    try:
        return Counter(d["code"] for d in json.loads(p.stdout or "[]"))
    except ValueError:
        return Counter()


def quality(old: dict[str, str], new: dict[str, str], diff_text: str, allow: list[str]) -> dict:
    """ast.parse OK, new ruff errors, lines changed, test file touched (policy.check_paths)."""
    new = {p: t for p, t in new.items() if old.get(p) != t}  # only files the edit changed
    parses, new_ruff = True, 0
    for p, t in new.items():
        if not p.endswith(".py"):
            continue
        try:
            ast.parse(t)
        except SyntaxError:
            parses = False
            continue
        delta = ruff_codes(t) - ruff_codes(old.get(p, ""))
        new_ruff += sum(delta.values())
    reasons = policy.check_paths(list(new), allow)
    res = policy.check_patch(diff_text, {p: old[p] for p in new if p in old}, new) if parses else None
    return {
        "ast_parse_ok": parses,
        "new_ruff_errors": new_ruff,
        "changed_lines": sum(
            1 for ln in diff_text.splitlines()
            if ln[:1] in "+-" and not ln.startswith(("+++", "---"))
        ),  # fmt: skip
        "touched_test_file": any(r.startswith("test_file") for r in reasons),
        "policy_reasons": reasons + (res.reasons if res else []),
        "policy_ok": not reasons and bool(res and res.ok),
    }


def apply_sr(reply: str, files: dict[str, str]) -> dict:
    """Parse + apply search/replace blocks. Returns status and new files if applicable."""
    try:
        blocks = edits.parse_blocks(reply)
    except edits.EditError as e:
        return {"format_ok": False, "applies": False, "error": e.reason}
    try:
        new = edits.apply_edits(files, blocks)
    except edits.EditError as e:
        return {"format_ok": True, "applies": False, "error": e.reason, "n_blocks": len(blocks)}
    return {"format_ok": True, "applies": True, "n_blocks": len(blocks), "new": new}


def strip_fence(text: str) -> tuple[str, bool]:
    m = re.search(r"```(?:diff|patch)?\s*\n(.*?)```", text, re.DOTALL)
    return (m.group(1), True) if m else (text, False)


def git_apply(diff: str, files: dict[str, str]) -> dict:
    """`git apply --check` (strict), `--recount` (lenient), then real apply for correctness."""
    d = Path(tempfile.mkdtemp(prefix="probe_git_"))
    try:
        subprocess.run(["git", "init", "-q"], cwd=d, check=True)
        for p, t in files.items():
            (d / p).parent.mkdir(parents=True, exist_ok=True)
            (d / p).write_text(t, encoding="utf-8", newline="\n")
        patch = d / "model.patch"
        patch.write_text(diff if diff.endswith("\n") else diff + "\n", encoding="utf-8", newline="\n")
        run = lambda *a: subprocess.run(  # noqa: E731
            ["git", "apply", *a, "model.patch"], cwd=d, capture_output=True, text=True
        )
        strict = run("--check")
        lenient = run("--check", "--recount")
        out: dict = {
            "strict_ok": strict.returncode == 0,
            "recount_ok": lenient.returncode == 0,
            "git_error": (strict.stderr.strip().splitlines() or [""])[0][:200],
        }
        if strict.returncode == 0:
            run()
            out["new"] = {p: (d / p).read_text(encoding="utf-8") for p in files}
        return out
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------- experiment 1: read limit
def est_tokens(chars: int) -> int:
    return int(chars / 3.0)  # conservative for code; real counts are recorded from the provider


def exp_read(cx: Ctx, args) -> dict:
    rows = []
    with GpuSampler() as gpu:
        for n in args.read_sizes:
            for t in range(args.tries):
                g = codegen.generate(n, seed=100 + t, bug_idx=[3, 6, 8][t % 3], bug_pos=[.2, .5, .8][t % 3])
                body = numbered(g["files"])
                row = {"target_lines": n, "try": t, "actual_lines": g["n_lines"],
                       "n_files": len(g["files"]), "bug_file": g["bug_file"],
                       "bug_line": g["bug_line"], "bug_name": g["bug_name"],
                       "prompt_chars": len(body)}  # fmt: skip
                if args.ctx and est_tokens(len(body)) + 600 > args.ctx:
                    row["status"] = "NOT RUN"
                    row["reason"] = (f"estimated {est_tokens(len(body))} prompt tokens (chars/3) "
                                     f"exceed ctx {args.ctx}")  # fmt: skip
                    rows.append(row)
                    continue
                user = (
                    f"One function in this code base has a bug.\nSymptom: {g['symptom']}\n\n"
                    f"{body}\n\nWhich file and which line contains the faulty statement? "
                    'Answer with JSON only: {"file": "<path>", "line": <line number>}'
                )
                r = cx.ask("You are a careful code reviewer.", user, max_tokens=100)
                row.update({k: v for k, v in r.items()})
                if "reply" in r:
                    m = re.search(r"\{.*?\}", r["reply"], re.DOTALL)
                    try:
                        ans = json.loads(m.group(0)) if m else {}
                    except ValueError:
                        ans = {}
                    row["answer"] = ans
                    fok = ans.get("file") == g["bug_file"]
                    try:
                        d = abs(int(ans.get("line")) - g["bug_line"])
                    except (TypeError, ValueError):
                        d = None
                    row["file_correct"] = fok
                    row["line_exact"] = fok and d == 0
                    row["line_within_2"] = fok and d is not None and d <= 2
                    row["parse_ok"] = bool(ans)
                    row["status"] = "ok"
                else:
                    row["status"] = "ERROR"
                rows.append(row)
                save("read_limit", _read_out(args, rows, gpu))
                if cx.stop_reason:
                    break
            if cx.stop_reason:
                break
    out = _read_out(args, rows, gpu)
    save("read_limit", out)
    return out


def _read_out(args, rows, gpu) -> dict:
    summ = {}
    for n in sorted({r["target_lines"] for r in rows}):
        rs = [r for r in rows if r["target_lines"] == n]
        done = [r for r in rs if r.get("status") == "ok"]
        summ[n] = {
            "tries_run": len(done), "tries_planned": len(rs),
            "exact": sum(r["line_exact"] for r in done),
            "within_2": sum(r["line_within_2"] for r in done),
            "file_correct": sum(r["file_correct"] for r in done),
            "mean_prompt_tokens": round(statistics.mean(r["tokens_in"] for r in done)) if done else None,
            "mean_latency_s": round(statistics.mean(r["latency_ms"] for r in done) / 1000, 1) if done else None,
            "status": "NOT RUN" if rs and all(r.get("status") == "NOT RUN" for r in rs) else "ok",
            "reason": next((r["reason"] for r in rs if r.get("reason")), None),
        }  # fmt: skip
    return {"experiment": "read_limit", "model": args.model, "provider": args.provider,
            "ctx": args.ctx, "summary": summ, "rows": rows, **gpu.summary()}  # fmt: skip


# ---------------------------------------------------------------- experiment 2/4: write limit
def exp_write(cx: Ctx, args) -> dict:
    rows = []
    with GpuSampler() as gpu:
        for n in args.write_sizes:
            for rep in range(args.write_reps):
                m = codegen.rates_module(n, seed=500 + rep)
                files = m["files"]
                row = {"target_changed_lines": n, "rep": rep, "n_changed_lines": m["n_changed_lines"],
                       "n_functions": m["n_functions"]}  # fmt: skip
                user = (
                    f"{plain(files)}\n\nEvery tax_* function in shop/rates.py must return the amount "
                    "plus tax at its own RATE constant, as its docstring says. Fix every function whose "
                    "body contradicts its docstring and leave correct functions untouched."
                )
                if args.ctx and est_tokens(len(user)) + 600 + args.max_out > args.ctx:
                    row.update(status="NOT RUN", reason=f"prompt+output budget exceeds ctx {args.ctx}")
                    rows.append(row)
                    continue
                r = cx.ask(SR_SPEC, user, max_tokens=args.max_out)
                row.update(r)
                if "reply" in r:
                    row["status"] = "ok"
                    a = apply_sr(r["reply"], files)
                    row.update({k: v for k, v in a.items() if k != "new"})
                    if a["applies"]:
                        new = {**files, **a["new"]}
                        diff = edits.to_unified_diff(files, new)
                        row["quality"] = quality(files, new, diff, ["shop/rates.py"])
                        exp = m["fixed"]["shop/rates.py"].splitlines()
                        got = new["shop/rates.py"].splitlines()
                        old = files["shop/rates.py"].splitlines()
                        need = [i for i in range(len(old)) if old[i] != exp[i]]
                        row["lines_needing_fix"] = len(need)
                        row["lines_fixed_correctly"] = sum(1 for i in need if len(got) == len(exp) and got[i] == exp[i])
                        row["collateral_wrong_lines"] = sum(
                            1 for i in range(len(old)) if i not in set(need) and len(got) == len(old) and got[i] != old[i]
                        )  # fmt: skip
                        row["exact_match_expected"] = new["shop/rates.py"] == m["fixed"]["shop/rates.py"]
                else:
                    row["status"] = "ERROR"
                rows.append(row)
                save("write_limit", _write_out(args, rows, gpu))
                if cx.stop_reason:
                    break
            if cx.stop_reason:
                break
    out = _write_out(args, rows, gpu)
    save("write_limit", out)
    return out


def _write_out(args, rows, gpu) -> dict:
    return {"experiment": "write_limit", "model": args.model, "provider": args.provider,
            "ctx": args.ctx, "max_output_tokens": args.max_out, "rows": rows, **gpu.summary()}  # fmt: skip


# ---------------------------------------------------------------- experiment 3: format comparison
def exp_format(cx: Ctx, args) -> dict:
    rows = []
    with GpuSampler() as gpu:
        for k in range(10):
            g = codegen.generate(55, seed=700 + k, bug_idx=k, bug_pos=0.5)
            fixed = codegen.fixed_version(g, k)
            files = {**g["files"], "tests/test_shop.py": "from shop.orders import *\n\n\ndef test_import():\n    assert True\n"}
            expected = fixed[g["bug_file"]]
            task = (
                f"{plain(files)}\n\nBug report: {g['symptom']}\n"
                "Fix the bug with the smallest possible change."
            )
            allow = [g["bug_file"]]
            for fmt, spec in (("search_replace", SR_SPEC), ("unified_diff", DIFF_SPEC)):
                row = {"fix": k, "bug_name": g["bug_name"], "format": fmt, "prompt_lines": sum(t.count("\n") for t in files.values())}
                r = cx.ask(spec, task, max_tokens=args.max_out)
                row.update(r)
                if "reply" not in r:
                    row["status"] = "ERROR"
                    rows.append(row)
                    if cx.stop_reason:
                        break
                    continue
                row["status"] = "ok"
                new = None
                if fmt == "search_replace":
                    a = apply_sr(r["reply"], files)
                    row.update({kk: v for kk, v in a.items() if kk != "new"})
                    row["applies_cleanly"] = a["applies"]
                    new = {**files, **a["new"]} if a["applies"] else None
                else:
                    diff, fenced = strip_fence(r["reply"])
                    row["fenced"] = fenced
                    ga = git_apply(diff, files)
                    row.update({kk: v for kk, v in ga.items() if kk != "new"})
                    row["applies_cleanly"] = ga["strict_ok"]
                    new = {**files, **ga["new"]} if ga["strict_ok"] else None
                if new is not None:
                    diff_text = edits.to_unified_diff(files, new)
                    row["quality"] = quality(files, new, diff_text, allow)
                    row["fix_correct"] = new.get(g["bug_file"]) == expected and all(
                        new[p] == files[p] for p in files if p != g["bug_file"]
                    )
                else:
                    row["fix_correct"] = False
                rows.append(row)
            save("format_comparison", _fmt_out(args, rows, gpu))
            if cx.stop_reason:
                break
    out = _fmt_out(args, rows, gpu)
    save("format_comparison", out)
    return out


def _fmt_out(args, rows, gpu) -> dict:
    summ = {}
    for f in ("search_replace", "unified_diff"):
        rs = [r for r in rows if r["format"] == f and r.get("status") == "ok"]
        summ[f] = {
            "n": len(rs), "applies_cleanly": sum(bool(r.get("applies_cleanly")) for r in rs),
            "fix_correct": sum(bool(r.get("fix_correct")) for r in rs),
            "recount_ok": sum(bool(r.get("recount_ok")) for r in rs) if f == "unified_diff" else None,
            "touched_test_file": sum(bool(r.get("quality", {}).get("touched_test_file")) for r in rs),
            "new_ruff_errors": sum(r.get("quality", {}).get("new_ruff_errors", 0) for r in rs),
            "ast_parse_fail": sum(1 for r in rs if r.get("quality") and not r["quality"]["ast_parse_ok"]),
        }  # fmt: skip
    return {"experiment": "format_comparison", "model": args.model, "provider": args.provider,
            "summary": summ, "rows": rows, **gpu.summary()}  # fmt: skip


# ---------------------------------------------------------------- experiment 5: rates/latency
def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def exp_rate(cx: Ctx, args) -> dict:
    """Aggregate latency and throughput from the real (non-cache-hit) calls saved by 1-3.
    Local Ollama has no request/token rate limit, so none can be observed."""
    calls = []
    peaks = {}
    for name in ("read_limit", "write_limit", "format_comparison"):
        f = RESULTS / f"{name}.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text("utf-8"))
        peaks[name] = {k: d.get(k) for k in ("vram_baseline_mib", "vram_peak_mib")}
        calls += [dict(r, experiment=name) for r in d["rows"] if "latency_ms" in r and r.get("status") != "ERROR"]
    out: dict = {"experiment": "rate_latency", "model": args.model, "provider": args.provider,
                 "n_calls": len(calls), "vram": peaks, "rate_limit_observed": None,
                 "rate_limit_note": "local Ollama has no request or token rate limit; "
                 "free-tier cloud limits (RPM/TPM/retry-after) were NOT measured (no keys, no cloud calls)."}  # fmt: skip
    if calls:
        lat = [c["latency_ms"] / 1000 for c in calls]
        tps = [c["tokens_out"] / (c["latency_ms"] / 1000) for c in calls if c["tokens_out"] > 20]
        out |= {
            "latency_s": {"p50": round(pct(lat, .5), 1), "p95": round(pct(lat, .95), 1),
                          "max": round(max(lat), 1)},  # fmt: skip
            "end_to_end_output_tokens_per_s": {"p50": round(pct(tps, .5), 1), "p95": round(pct(tps, .95), 1)} if tps else None,
            "tokens_in_total": sum(c["tokens_in"] for c in calls),
            "tokens_out_total": sum(c["tokens_out"] for c in calls),
            "failures": sum(1 for c in calls if c.get("status") == "ERROR"),
            "by_prompt_size": _by_size(calls),
        }
        # gateway log counts errors too
    log = RESULTS / "llm_calls.jsonl"
    if log.exists():
        recs = [json.loads(x) for x in log.read_text("utf-8").splitlines() if x.strip()]
        out["gateway_log"] = {"records": len(recs), "failed": sum(1 for r in recs if not r.get("ok")),
                              "cache_hits": sum(1 for r in recs if r.get("cache_hit"))}  # fmt: skip
    save("rate_latency", out)
    return out


def _by_size(calls: list[dict]) -> dict:
    buckets = {"<2k": (0, 2000), "2k-6k": (2000, 6000), "6k-12k": (6000, 12000), ">12k": (12000, 10**9)}
    res = {}
    for k, (lo, hi) in buckets.items():
        rs = [c for c in calls if lo <= c["tokens_in"] < hi]
        if rs:
            lat = [c["latency_ms"] / 1000 for c in rs]
            res[k] = {"n": len(rs), "latency_p50_s": round(pct(lat, .5), 1), "latency_max_s": round(max(lat), 1)}
    return res


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--exp", default="all", help="read,write,format,rate or all (comma list)")
    ap.add_argument("--provider", default="ollama")
    ap.add_argument("--model", default="qwen2.5-coder-7b-ctx16k",
                    help="for Ollama this is a Modelfile variant of qwen2.5-coder:7b with num_ctx set")
    ap.add_argument("--ollama-url", default="http://localhost:11434/v1")
    ap.add_argument("--ctx", type=int, default=16384, help="context window tokens (skip sizes that cannot fit)")
    ap.add_argument("--read-sizes", type=lambda s: [int(x) for x in s.split(",")], default=[100, 300, 1000, 3000])
    ap.add_argument("--write-sizes", type=lambda s: [int(x) for x in s.split(",")], default=[5, 20, 50, 100])
    ap.add_argument("--write-reps", type=int, default=2)
    ap.add_argument("--tries", type=int, default=3)
    ap.add_argument("--max-out", type=int, default=6000)
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()
    exps = ["read", "write", "format", "rate"] if args.exp == "all" else args.exp.split(",")
    cx = Ctx(args)
    RESULTS.mkdir(parents=True, exist_ok=True)
    save("environment", {"model": args.model, "provider": args.provider, "ctx": args.ctx,
                         "hardware": hardware(args), "date": time.strftime("%Y-%m-%d %H:%M")})  # fmt: skip
    fns = {"read": exp_read, "write": exp_write, "format": exp_format, "rate": exp_rate}
    for e in exps:
        print(f"== {e}", flush=True)
        out = fns[e](cx, args)
        print(json.dumps(out.get("summary", {k: v for k, v in out.items() if k != "rows"}), indent=1)[:3000])
        if cx.stop_reason:
            print("STOPPED:", cx.stop_reason)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
