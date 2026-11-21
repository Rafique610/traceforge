# ruff: noqa: E501
"""Collect a REAL EvidenceBundle for a seed case from a live, isolated lab started from its faulty tree.

    python -m traceforge.agent.lab_collect --case shop_api-001 [--out runs/evidence]

Per case: materialise the faulty tree (generator output, never model-visible), start the lab FROM THAT
TREE as its own compose project (`tf-e2e-<n>`, free host ports, own image tags, so the user's lab, images
and containers are never touched), trigger the real failure, collect with `EvidenceCollector` through the
read-only Docker proxy (must already be up), validate against the contract, check no lab secret leaked,
tear the project down (`down -v` of this project's own volume only).

Triggers follow the case template: config/code cases send a real POST /orders; runtime cases stop the
dependency named in runtime.yaml; `logs: suppressed` starts the app containers with the `none` log driver.
Case 001's fault is a wrong *default*, which the lab compose masks with REDIS_HOST=lab_redis, so for this
disposable copy only that variable is removed from the compose file (documented deviation, see `notes`).
"""

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from traceforge.contracts.case_manifest import CaseManifest
from traceforge.contracts.evidence import EvidenceBundle
from traceforge.evidence import EvidenceCollector
from traceforge.evidence.model import EvidenceConfig

REPO = Path(__file__).resolve().parents[3]
PROXY_FILE = REPO / "backend/traceforge/evidence/docker-proxy.compose.yaml"
SCRATCH = Path(os.environ.get("TF_E2E_SCRATCH", "D:/AI/tmp/e2e"))


def sh(args: list[str], timeout: int = 600, check: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)  # noqa: S603
    if check and p.returncode:
        raise RuntimeError(f"{args[:4]} failed: {p.stderr[-800:]}")
    return p


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def materialize_tree(case_id: str, tree: Path) -> Path:
    ds = SCRATCH / "datasets"  # generator writes here, so the repo datasets stay untouched
    py = [sys.executable, "-m", "traceforge.faultgen.generate", "--datasets", str(ds)]
    sh([*py, "--tree-out", str(tree), "--case", case_id], 300)
    return tree


def _post_order(port: int, qty: int) -> str:
    def call(path: str, body: dict | None = None) -> tuple[int, str]:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as r:  # noqa: S310
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()

    code, text = call("/products")
    pid = json.loads(text if code == 200 else "[]")[0]["id"] if code == 200 else 1
    body = {"customer_email": "buyer@example.org", "items": [{"product_id": pid, "quantity": qty}]}
    try:
        code, text = call("/orders", body)
    except OSError as e:
        return f"POST /orders quantity={qty} -> no response in 90 s ({type(e).__name__})"
    return f"POST /orders quantity={qty} -> {code} {text[:120]}"


def run_lab(case: CaseManifest, tree: Path, runtime: dict, tag: str) -> tuple[Path, str, int, dict]:
    """Prepare the compose files for the tree; returns (lab tree dir, project, api port, notes)."""
    notes: dict = {}
    lab_tree = tree
    compose = tree / "lab/compose.yaml"
    if case.fault_family == "wrong_host":  # compose masks the faulty default: remove it (copy only)
        lab_tree = tree.parent / f"{tree.name}-live"
        import shutil

        shutil.rmtree(lab_tree, ignore_errors=True)
        shutil.copytree(tree, lab_tree)
        compose = lab_tree / "lab/compose.yaml"
        text = compose.read_text("utf-8")
        text = text.replace("    REDIS_HOST: lab_redis\n", "", 1)
        keep = "    image: traceforge-lab/worker:dev\n"  # the worker keeps its REDIS_HOST
        extra = "    environment:\n      <<: *app-env\n      REDIS_HOST: lab_redis\n"
        text = text.replace(keep, keep + extra, 1)
        compose.write_text(text, "utf-8")
        notes["compose_modified"] = "removed REDIS_HOST from shop_api's env only (disposable copy)"
    return lab_tree, f"tf-e2e-{tag}", free_port(), notes


def _tolerate_no_logs() -> None:
    from docker.errors import APIError

    from traceforge.evidence import docker_read

    orig = docker_read.read_logs

    def read_logs(client, cfg, service):  # noqa: ANN001
        try:
            return orig(client, cfg, service)
        except APIError:
            return ""

    docker_read.read_logs = read_logs


def collect_case(case: CaseManifest, datasets: Path, out_dir: Path, keep_up: bool = False) -> dict:
    tag = case.case_id.split("-")[-1]
    tree = materialize_tree(case.case_id, SCRATCH / "trees" / case.case_id)
    meta = json.loads((datasets / "cases" / case.case_id / "meta.json").read_text("utf-8"))
    runtime = meta.get("runtime", {})
    lab_tree, project, port, notes = run_lab(case, tree, runtime, tag)
    api_port, redis_port = port, free_port()
    ov = SCRATCH / f"override-{tag}.yaml"
    log = {"logging": {"driver": "none"}} if runtime.get("logs") == "suppressed" else {}
    ov.write_text(
        "services:\n"
        f"  shop_api:\n    image: tf-e2e/shop_api:{tag}\n"
        + ("    logging:\n      driver: none\n" if log else "")
        + f"  worker:\n    image: tf-e2e/worker:{tag}\n"
        + ("    logging:\n      driver: none\n" if log else ""),
        "utf-8",
    )
    env = (REPO / "lab/.env").read_text("utf-8").lstrip("\ufeff")
    env = re.sub(r"(?m)^LAB_API_PORT=.*$", f"LAB_API_PORT={api_port}", env)
    env = re.sub(r"(?m)^LAB_REDIS_PORT=.*$", f"LAB_REDIS_PORT={redis_port}", env)
    envfile = SCRATCH / f"env-{tag}"
    envfile.write_text(env, "utf-8")
    dc = ["docker", "compose", "-p", project, "--env-file", str(envfile),
          "-f", str(lab_tree / "lab/compose.yaml"), "-f", str(ov)]  # fmt: skip
    steps: list[str] = []
    try:
        sh([*dc, "up", "-d", "--build", "--wait"], 900)
        steps.append("lab up (built from the faulty tree)")
        sh([*dc, "exec", "-T", "shop_api", "python", "-m", "app.seed"], 60)
        steps.append("seeded catalogue (python -m app.seed)")
        for dep in runtime.get("stop", []):
            sh([*dc, "stop", dep])
            steps.append(f"stopped {dep}")
        if "stop" in runtime or case.cause_class in ("application_code", "configuration"):
            qty = 100 if case.fault_family == "boundary" else 1
            steps.append(_post_order(api_port, qty))
        else:
            steps.append("no request sent (intermittent symptom, logs suppressed)")
        time.sleep(2)
        cfg = EvidenceConfig(
            repo_root=lab_tree, compose_project=project,
            probes={"shop_api": f"http://127.0.0.1:{api_port}/health"},
        )  # fmt: skip
        if runtime.get("logs") == "suppressed":
            notes["collector_gap"] = (
                "docker_read.read_logs raises APIError 501 for the 'none' log driver; "
                "adapter treats it as empty logs (collector itself is unchanged)"
            )
            _tolerate_no_logs()
        col = EvidenceCollector(cfg).collect_detailed(f"inc-{case.case_id}", case.service, case)
    finally:
        if not keep_up:
            sh([*dc, "down", "-v", "--remove-orphans"], 300, check=False)
            for img in (f"tf-e2e/shop_api:{tag}", f"tf-e2e/worker:{tag}"):
                sh(["docker", "rmi", img], 60, check=False)
    bundle = EvidenceBundle.model_validate(col.bundle.model_dump(mode="json"))
    text = bundle.model_dump_json(indent=1)
    leaks = [v for v in re.findall(r"(?m)^LAB_DB_PASSWORD=(.+)$", env) if v and v in text]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{case.case_id}.json").write_text(text, "utf-8")
    kinds: dict[str, int] = {}
    for i in bundle.items:
        kinds[i.kind] = kinds.get(i.kind, 0) + 1
    return {
        "case_id": case.case_id, "items": len(bundle.items), "kinds": kinds,
        "log_ids": [i.id for i in bundle.items if i.kind == "log"],
        "frame_ids": [i.id for i in bundle.items if i.kind == "trace_frame"],
        "frame_paths": [f"{i.path}:{i.line}" for i in bundle.items if i.kind == "trace_frame"],
        "log_format": col.log_format, "warnings": col.warnings, "steps": steps, "notes": notes,
        "secret_leak": bool(leaks), "contract_valid": True,
    }  # fmt: skip


def proxy(up: bool) -> None:
    f = ["docker", "compose", "-f", str(PROXY_FILE)]
    sh([*f, "up", "-d", "--wait"] if up else [*f, "down"], 300, check=up)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--case", action="append", required=True)
    ap.add_argument("--manifest", type=Path, default=REPO / "datasets/manifests/dev.json")
    ap.add_argument("--out", type=Path, default=Path("runs/evidence"))
    a = ap.parse_args(argv)
    rows = {
        r["case_id"]: CaseManifest.model_validate(r)
        for r in json.loads(a.manifest.read_text("utf-8"))
    }
    proxy(True)
    try:
        for cid in a.case:
            print(json.dumps(collect_case(rows[cid], a.manifest.parents[1], a.out), indent=1))
    finally:
        proxy(False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
