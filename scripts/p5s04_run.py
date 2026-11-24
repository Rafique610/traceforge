"""P5-S04 driver: G1 with local Ollama model on the 12 RC1 stage-1 sites, sequential, HwMonitor per case.

Run from backend/ with its venv:  .venv/Scripts/python.exe ../scripts/p5s04_run.py
Local Ollama only. Writes runs/p5s04/** and results/p5s04/hw/**; never touches results/final or datasets.
"""
import json, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACK = REPO / "backend"
sys.path.insert(0, str(BACK))
from traceforge.agent.hw_monitor import HwMonitor  # noqa: E402

MODEL = "qwen3.5-4b-ctx12k"
CASE_TIMEOUT_S = 12 * 60
BUDGET_S = 62 * 60
_sel = json.loads((REPO / "results/final/selection-rc1.json").read_text("utf-8"))["cases"]
# interleave strata so every cause class is covered if the wall-time budget truncates the run
cases = [_sel[i] for i in (0, 6, 10, 11, 1, 7, 2, 8, 3, 9, 4, 5)]
(REPO / "results/p5s04/hw").mkdir(parents=True, exist_ok=True)
t_all = time.time()
for c in cases:
    rid = f"p5s04-{c}-G1-qwen35-4b-ctx12k-r0"
    done = REPO / f"results/p5s04/hw/{c}.json"
    if done.exists():
        continue
    if time.time() - t_all > BUDGET_S:
        done.write_text(json.dumps({"case": c, "status": "not_run_budget_exhausted"}), "utf-8")
        continue
    cmd = [str(BACK / ".venv/Scripts/python.exe"), "-m", "traceforge.agent.e2e", "--case", c,
           "--condition", "G1", "--provider", "ollama", "--model", MODEL,
           "--label", "EXPERIMENTAL-LOCAL-P5S04", "--manifest", str(REPO / "datasets/manifests/test.json"),
           "--no-db", "--out", str(REPO / "runs/p5s04"), "--run-id", rid]
    t0 = time.time()
    status, tail = "ok", ""
    with HwMonitor(interval_s=2.0) as hw:
        try:
            p = subprocess.run(cmd, cwd=BACK, capture_output=True, text=True, timeout=CASE_TIMEOUT_S)
            tail = (p.stdout + p.stderr)[-1500:]
            if p.returncode:
                status = f"exit_{p.returncode}"
        except subprocess.TimeoutExpired as e:
            status = "timeout_12min"
            tail = str(e.stderr or "")[-500:]
    wall = time.time() - t0
    done.write_text(json.dumps({"case": c, "run_id": rid, "status": status, "wall_s": round(wall, 1),
                                "hw": hw.summary(), "tail": tail}, indent=1), "utf-8")
    print(c, status, round(wall), hw.summary(), flush=True)
