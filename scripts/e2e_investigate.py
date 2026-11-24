"""Drive the real investigation workflow over HTTP (through the vite proxy by default).

    python scripts/e2e_investigate.py --case shop_api-017 --decision approve [--base http://localhost:5173/api]

Creates an incident, POSTs /investigate, polls to REVIEW_PENDING, prints a report summary,
submits the review, then prints the audit trail. Stdlib only; never reads keys.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def call(base: str, method: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--decision", choices=["approve", "reject"], required=True)
    ap.add_argument("--base", default="http://localhost:5173/api")
    ap.add_argument("--out", default="runs/real-e2e")
    ap.add_argument("--timeout", type=int, default=1800)
    a = ap.parse_args()
    t0 = time.time()
    st, inc = call(a.base, "POST", "/incidents", {"case_id": a.case})
    print("create", st, inc.get("id"), inc.get("state"))
    iid = inc["id"]
    st, r = call(a.base, "POST", f"/incidents/{iid}/investigate")
    print("investigate", st, r)
    if st != 202:
        return 1
    last = None
    while time.time() - t0 < a.timeout:
        _, cur = call(a.base, "GET", f"/incidents/{iid}")
        if cur["state"] != last:
            last = cur["state"]
            print(f"[{time.time() - t0:7.1f}s] state={last}", flush=True)
        _, ev = call(a.base, "GET", f"/incidents/{iid}/events")
        if any(e["event_type"] == "investigation_failed" for e in ev):
            print("FAILED", [e["payload"] for e in ev if e["event_type"] == "investigation_failed"])
            return 2
        if last == "REVIEW_PENDING":
            break
        time.sleep(5)
    else:
        print("timeout")
        return 3
    print(f"investigation seconds: {time.time() - t0:.1f}")
    _, rep = call(a.base, "GET", f"/incidents/{iid}/report")
    with open(f"{a.out}/report-{a.case}.json", "w") as f:
        json.dump(rep, f, indent=1)
    sha = (rep.get("patch") or {}).get("sha256")
    body = {"decision": a.decision, "reviewer": "e2e-human", "comment": f"e2e {a.decision}"}
    if sha:
        body["patch_sha256"] = sha
    st, rv = call(a.base, "POST", f"/incidents/{iid}/review", body)
    print("review", st, rv)
    _, cur = call(a.base, "GET", f"/incidents/{iid}")
    print("final state", cur["state"])
    _, ev = call(a.base, "GET", f"/incidents/{iid}/events")
    with open(f"{a.out}/events-{a.case}.json", "w") as f:
        json.dump(ev, f, indent=1)
    for e in ev:
        print(e["id"], e["actor"], e["event_type"], e["from_state"], "->", e["to_state"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
