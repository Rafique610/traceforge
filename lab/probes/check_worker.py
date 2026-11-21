"""Probe: does the `worker:heartbeat` key exist in the lab Redis? Exit 0 if yes.

Speaks raw RESP over a socket so the host needs no Redis client.
Usage: python lab/probes/check_worker.py [--host 127.0.0.1] [--port 6380]
"""

import argparse
import socket
import sys

KEY = "worker:heartbeat"


def probe(host: str, port: int) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=3) as s:
            s.sendall(f"*2\r\n$6\r\nEXISTS\r\n${len(KEY)}\r\n{KEY}\r\n".encode())
            reply = s.recv(64).decode().strip()
    except OSError as exc:
        return False, f"redis unreachable: {exc}"
    return reply == ":1", f"{KEY} {'present' if reply == ':1' else 'missing'}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=6380)
    a = ap.parse_args()
    ok, detail = probe(a.host, a.port)
    print(("OK " if ok else "FAIL ") + detail)
    sys.exit(0 if ok else 1)
