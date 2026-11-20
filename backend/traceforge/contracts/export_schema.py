"""Write JSON Schema for every contract: `task contracts:schema`."""

import json
from pathlib import Path

from traceforge.contracts import CONTRACTS

OUT = Path(__file__).parent / "schema"

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for name, model in CONTRACTS.items():
        path = OUT / f"{name}.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8")
        print(path.relative_to(Path.cwd()).as_posix())
