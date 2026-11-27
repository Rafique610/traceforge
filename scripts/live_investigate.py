"""Live (or zero-token) run of ONE case through the REAL Investigate path: real repo build, real symptom
run in the sandbox, real evidence, retrieval, pipeline, patch apply, sandbox validation, report, review states.
Default: the model is a scripted stand-in that submits the known diagnosis and fix (tests our wiring, 0 tokens).
REAL_MODEL=1 uses the real gateway (provider from TRACEFORGE_LLM_*). MANIFEST=<path> picks the manifest
(default datasets/manifests/dev.json; BugsInPy: datasets/manifests/bugsinpy.json). Run from backend/:
    python ../scripts/live_investigate.py shop_api-002
"""

import json
import re
import sys
import uuid
from pathlib import Path

BACKEND = Path.cwd()
sys.path[:0] = [str(BACKEND / "tests" / "agent"), str(BACKEND / "tests")]

from agentfakes import call, resp  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from traceforge import investigation  # noqa: E402
from traceforge.config import Settings, get_settings  # noqa: E402
from traceforge.database import Base, get_db  # noqa: E402
from traceforge.incidents import models as _m  # noqa: E402,F401
from traceforge.incidents import service  # noqa: E402
from traceforge.incidents.router import register_handlers  # noqa: E402
from traceforge.incidents.router import router as incidents_router  # noqa: E402
from traceforge.incidents.schemas import IncidentCreate  # noqa: E402
from traceforge.repair import models as _r  # noqa: E402,F401

CASE = sys.argv[1] if len(sys.argv) > 1 else "shop_api-002"
REPO = BACKEND.parent
import os as _o
MANIFEST = Path(_o.environ.get("MANIFEST") or REPO / "datasets" / "manifests" / "dev.json")
case = next(c for c in json.loads(MANIFEST.read_text("utf-8")) if c["case_id"] == CASE)
BIP = case.get("origin") == "bugsinpy"  # real fix: SEARCH old (-), REPLACE new (+)
patch = (REPO / "runs/external/bugsinpy" / CASE / "fix.patch").read_text("utf-8") if BIP else (REPO / "datasets" / "cases" / CASE / "mutation.patch").read_text("utf-8")


def gold_fix() -> str:
    """SEARCH the faulty lines (+) and REPLACE with the original lines (-), per hunk."""
    blocks, path = [], None
    for hunk in re.split(r"^(?=@@|\+\+\+ )", patch, flags=re.M):
        if hunk.startswith("+++ "):
            path = hunk.split()[1].removeprefix("b/")
            path = f"lab/{case['service']}/{path}" if BIP else path
            continue
        if not hunk.startswith("@@"):
            continue
        lines = hunk.splitlines()[1:]
        old = [ln[1:] for ln in lines if ln[:1] in (" ", "-" if BIP else "+")]
        new = [ln[1:] for ln in lines if ln[:1] in (" ", "+" if BIP else "-")]
        blocks.append(f"<<<<<<< SEARCH {path}\n" + "\n".join(old) + "\n=======\n"
                      + "\n".join(new) + "\n>>>>>>> REPLACE")  # fmt: skip
    return "\n".join(blocks)


class StandIn:
    """Diagnosis call (tools offered) -> submit gold target with cited evidence ids; patch call -> gold fix."""

    def __init__(self):
        self.calls, self.prompts = [], []

    def __call__(self, messages, tools=None, **kw):
        text = json.dumps(messages)
        self.prompts.append(text)
        self.calls.append("diagnosis" if tools else "patch")
        import os
        if os.environ.get("CAPTURE") and len(self.calls) == 1:
            Path(os.environ["CAPTURE"]).write_text(json.dumps({"messages": messages, "tools": tools}), "utf-8")
        last = str(messages[-1].get("content", ""))
        if "ERROR" in last: print("TOOL ERROR SEEN BY MODEL:", last[:600])
        if tools:
            sym = re.findall(r"\[(EV-\d{4})\] SYMPTOM", text)
            ids = (sym + [i for i in sorted(set(re.findall(r"EV-\d{4}", text))) if i not in sym])[:3]
            if case["gold_config_keys"]:  # cite the items that mention the key, as a model must
                key = case["gold_config_keys"][0].split(".")[-1].lower()
                parts = re.split(r"\[(EV-\d{4})[ \]]", text)
                hits = [parts[i] for i in range(1, len(parts) - 1, 2) if key in parts[i + 1][:600].lower()]
                ids = list(dict.fromkeys(sym[:1] + hits))[:4]
            g = dict(case["gold_symbols"][0]) if case["gold_symbols"] else {}
            if "does not exi" in last and "." in g.get("qualname", ""):
                g["qualname"] = g["qualname"].rsplit(".", 1)[0]  # field -> its class
            args = {"cause_class": case["cause_class"], "supporting_evidence_ids": ids,
                    "rationale": "stand-in: known diagnosis", "confidence": "high", "observed_symptom": "visible order test fails on a boundary quantity"}  # fmt: skip
            if case["gold_config_keys"]:
                args["config_key"] = case["gold_config_keys"][0]
            else:
                args |= {"path": g["path"], "qualname": g["qualname"]}
            return resp(call("submit_diagnosis", **args))
        return resp(content=gold_fix())


fake = StandIn()


class RealPathFakeModel(investigation.InvestigationFactory):
    def check(self, settings, incident):  # skip only the provider-key check
        if not settings.manifest:
            raise RuntimeError("TRACEFORGE_MANIFEST not set")

    def build(self, settings, incident):
        plan = super().build(settings, incident)
        plan.chat_fn = fake
        return plan


settings = Settings(manifest=str(MANIFEST), evidence_dir=REPO / "runs" / "evidence")
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(engine)
sf = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def db():
    with sf() as s:
        yield s


app = FastAPI()
app.include_router(incidents_router)
app.include_router(investigation.router)
register_handlers(app)
app.dependency_overrides[get_db] = db
app.dependency_overrides[investigation.get_session_factory] = lambda: sf
import os as _os
REAL = bool(_os.environ.get("REAL_MODEL"))  # use the real gateway (provider from TRACEFORGE_LLM_*)
app.dependency_overrides[investigation.get_factory] = (
    (lambda: investigation.InvestigationFactory()) if REAL else (lambda: RealPathFakeModel())
)
app.dependency_overrides[get_settings] = lambda: settings
client = TestClient(app)

with sf() as s:
    iid = str(service.create_incident(s, IncidentCreate(case_id=CASE, service=case["service"])).id)
r = client.post(f"/incidents/{iid}/investigate")
print("POST investigate:", r.status_code, r.text[:200])
inc = client.get(f"/incidents/{iid}").json()
events = client.get(f"/incidents/{iid}/events").json()
print("final state:", inc["state"], "| cause:", inc.get("cause_class"))
[print(" ", e.get("from_state"), "->", e.get("to_state"), json.dumps(e.get("payload"))[:400]) for e in events]
for e in events:
    p = e.get("payload") or {}
    if any(k in p for k in ("error", "reason", "failure_reason", "outcome", "detail")):
        print("  ", e["to_state"], {k: p[k] for k in p if k in ("error", "reason", "failure_reason", "outcome", "detail")})
print("model calls:", fake.calls)
print("hidden-test text in prompts:", any("hidden_tests" in p for p in fake.prompts))
print("fix sent:\n" + gold_fix())
import os
if os.environ.get("DUMP"):
    t = json.loads(fake.prompts[0])[1]["content"]
    for m in re.finditer(r"discount", t, re.I):
        print("...", t[max(0, m.start()-160):m.start()+80].replace("\n", " | "))
    print("ids in symptom/evidence:", re.findall(r"\[(EV-\d{4})\][^\n]{0,60}", t)[:40])
