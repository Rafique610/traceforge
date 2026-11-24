"""Exit 1 if the code fingerprint differs from the frozen RC file given as the argument."""

import sys
from pathlib import Path

from traceforge.evaluation.fingerprint import code_fingerprint

if __name__ == "__main__":
    want = Path(sys.argv[1]).read_text("utf-8").strip()
    got = code_fingerprint()["sha256"]
    print(
        "fingerprint ok"
        if got == want
        else f"FINGERPRINT MISMATCH: frozen {want[:12]} now {got[:12]}"
    )
    raise SystemExit(0 if got == want else 1)
