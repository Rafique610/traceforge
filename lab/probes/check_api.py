"""Probe: GET /health on the shop API. Exit 0 if status ok, 1 otherwise. Prints the body.

Usage: python lab/probes/check_api.py [--url http://127.0.0.1:8100]
"""

import argparse
import json
import sys
import urllib.error
import urllib.request


def probe(url: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=5) as r:
            body = r.read().decode()
    except urllib.error.HTTPError as exc:  # 503 carries the degraded body
        body = exc.read().decode()
    except OSError as exc:
        return False, f"unreachable: {exc}"
    try:
        return json.loads(body).get("status") == "ok", body
    except ValueError:
        return False, body


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8100")
    ok, detail = probe(ap.parse_args().url.rstrip("/"))
    print(("OK " if ok else "FAIL ") + detail)
    sys.exit(0 if ok else 1)
