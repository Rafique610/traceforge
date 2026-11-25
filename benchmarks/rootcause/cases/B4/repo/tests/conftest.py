import os
import pathlib

import yaml

_doc = yaml.safe_load((pathlib.Path(__file__).resolve().parent.parent / "compose.yaml").read_text())
for _k, _v in (_doc["services"]["api"].get("environment") or {}).items():
    os.environ[_k] = str(_v)
