# ruff: noqa: E501
"""Sync-1 integration: offline manifest replay, and route -> pipeline -> repair -> report -> review.

No provider or model is called: every gateway is a scripted fake. SQLite stand-in (as other tests);
the repair loop runs real pytest in a temporary git repo (as tests/repair does).
"""

import json
import sys
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

TESTS = Path(__file__).parents[1]
sys.path[:0] = [str(TESTS / "agent"), str(TESTS / "repair")]
from agentfakes import SUBMIT_CODE, FakeChat, call, resp  # noqa: E402
from gitrepo import make_repo, pytest_runner  # noqa: E402

from traceforge import investigation  # noqa: E402
from traceforge.agent.pipeline import Sources, run_case, sample_sources  # noqa: E402
from traceforge.agent.real_sources import LabEvidenceSource, ManifestCaseSource  # noqa: E402
from traceforge.agent.sources import SampleContextSource  # noqa: E402
from traceforge.config import Settings, get_settings  # noqa: E402
from traceforge.contracts.agent_run import AgentRunRecord  # noqa: E402
from traceforge.contracts.context import ContextBundle  # noqa: E402
from traceforge.contracts.evidence import EvidenceBundle  # noqa: E402
from traceforge.database import Base, get_db  # noqa: E402
from traceforge.incidents import models as _m  # noqa: E402,F401
from traceforge.incidents import repository, service  # noqa: E402
from traceforge.incidents.router import register_handlers as register_incident_handlers  # noqa: E402
from traceforge.incidents.router import router as incidents_router  # noqa: E402
from traceforge.incidents.schemas import IncidentCreate  # noqa: E402
from traceforge.incidents.states import State  # noqa: E402
from traceforge.repair import models as _r  # noqa: E402,F401
from traceforge.reports.router import router as report_router  # noqa: E402
from traceforge.reports.schemas import Report  # noqa: E402
from traceforge.reviews import models as _rv  # noqa: E402,F401
from traceforge.reviews.router import register_handlers as register_review_handlers  # noqa: E402
from traceforge.reviews.router import router as review_router  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
MANIFEST = REPO / "datasets/manifests/dev.json"
EVIDENCE = REPO / "runs/evidence"

HIDDEN = "HIDDEN_MARK_zz"
FILES = {
    "shop.py": "def discount(price, pct):\n    return price - price * pct\n",
    "tests/test_repro.py": "from shop import discount\n\n\ndef test_a():\n    assert discount(200, 10) == 180\n",
    "tests/test_visible.py": "from shop import discount\n\n\ndef test_zero():\n    assert discount(100, 0) == 100\n",
    "tests/test_hidden.py": f"from shop import discount\n\n\ndef test_{HIDDEN}():\n    assert discount(50, 50) == 25\n",
}
FIX = "<<<<<<< SEARCH shop.py\n    return price - price * pct\n=======\n    return price - price * pct / 100\n>>>>>>> REPLACE"


class SampleCtx(SampleContextSource):
    def read_symbol(self, case, path, qualname):
        return "def discount(price, pct):\n    return price - price * pct"


class NoHits:
    """Context source with no retrieval hits (the replay uses a real manifest case + saved evidence)."""

    def retrieve(self, evidence, graph, mode, token_budget):
        return ContextBundle(
            incident_id=evidence.incident_id, mode=mode, token_budget=token_budget,
            tokens_used=0, hits=[],
        )  # fmt: skip

    def read_symbol(self, case, path, qualname):
        return None

    def neighbors(self, node_id):
        return []


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _clean_running():
    investigation._running.clear()
    yield
    investigation._running.clear()


# ---- 1. offline replay of a real dev manifest case ---------------------------------------------


@pytest.mark.skipif(not (EVIDENCE / "shop_api-001.json").is_file(), reason="no saved evidence")
def test_manifest_case_replay_persists_schema_valid_rows(session_factory):
    cases = ManifestCaseSource(MANIFEST)
    case = cases.get("shop_api-001")
    src = Sources(cases, LabEvidenceSource(EVIDENCE), NoHits())
    bundle = EvidenceBundle.model_validate_json((EVIDENCE / "shop_api-001.json").read_text("utf-8"))
    ids = [i.id for i in bundle.items][:2]
    submit = call(
        "submit_diagnosis", cause_class="configuration", config_key="shop_api.REDIS_HOST",
        supporting_evidence_ids=ids, rationale="wrong broker host default",
    )  # fmt: skip
    chat = FakeChat(
        resp(submit), resp(content="<<<<<<< SEARCH x.py\na\n=======\nb\n>>>>>>> REPLACE")
    )
    with session_factory() as db:
        inc = service.create_incident(
            db, IncidentCreate(case_id=case.case_id, service=case.service)
        )
        rec = run_case(inc, "G1", src, db=db, settings=Settings(), chat_fn=chat,
                       dataset_sha256=cases.sha256)  # fmt: skip
        AgentRunRecord.model_validate(rec.model_dump())
        assert rec.case_id == "shop_api-001" and rec.diagnosis.target == "shop_api.REDIS_HOST"
        assert rec.dataset_sha256 == cases.sha256 and rec.git_sha == case.base_sha
        rows = repository.list_evidence(db, inc.id)
        assert {r.id for r in rows} == {i.id for i in bundle.items}
        events = repository.list_events(db, inc.id)
        assert [e.to_state for e in events][:5] == [
            State.CREATED, State.SNAPSHOT_LOCKED, State.EVIDENCE_COLLECTED,
            State.CONTEXT_RETRIEVED, State.DIAGNOSED,
        ]  # fmt: skip
        diagnosed = next(e for e in events if e.to_state is State.DIAGNOSED)
        assert diagnosed.payload["evidence_ids"] == ids
        assert diagnosed.payload["target"] == "shop_api.REDIS_HOST"


# ---- 2. route -> pipeline -> repair -> report -> review -----------------------------------------


class FakeFactory(investigation.InvestigationFactory):
    def __init__(self, chat, repo=None, *, fail=False):
        self.chat, self.repo, self.fail = chat, repo, fail

    def check(self, settings, incident):  # no provider/manifest needed for the fake gateway
        return None

    def build(self, settings, incident):
        if self.fail:
            raise RuntimeError("boom")
        s = sample_sources()
        path, sha = self.repo
        return investigation.Plan(
            sources=Sources(s.cases, s.evidence, SampleCtx()), chat_fn=self.chat,
            run_tests=pytest_runner, repo_path=path, base_sha=sha, allowlist=["shop.py"],
            visible_test_sources=[FILES["tests/test_visible.py"]], condition="G0",
            settings=Settings(),
        )  # fmt: skip


def make_client(session_factory, factory):
    def override_db():
        with session_factory() as session:
            yield session

    app = FastAPI()
    for r in (incidents_router, investigation.router, report_router, review_router):
        app.include_router(r)
    register_incident_handlers(app)
    register_review_handlers(app)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[investigation.get_session_factory] = lambda: session_factory
    app.dependency_overrides[investigation.get_factory] = lambda: factory
    app.dependency_overrides[get_settings] = lambda: Settings()
    return TestClient(app)


def new_incident(session_factory, case_id="code"):
    with session_factory() as db:
        return str(
            service.create_incident(db, IncidentCreate(case_id=case_id, service="shop_api")).id
        )


def test_route_pipeline_repair_report_review_end_to_end(session_factory, tmp_path):
    repo = make_repo(tmp_path / "r", FILES)
    chat = FakeChat(resp(SUBMIT_CODE), resp(content=FIX))
    client = make_client(session_factory, FakeFactory(chat, repo))
    iid = new_incident(session_factory)

    r = client.post(f"/incidents/{iid}/investigate")
    assert r.status_code == 202 and r.json() == {"status": "started", "incident_id": iid}
    assert uuid.UUID(iid) not in investigation._running  # job done, lock released

    inc = client.get(f"/incidents/{iid}").json()
    assert inc["state"] == "REVIEW_PENDING" and inc["cause_class"] == "application_code"
    states = [e["to_state"] for e in client.get(f"/incidents/{iid}/events").json()]
    assert "DIAGNOSED" in states and "PATCH_PROPOSED" in states and "VERIFIED" in states
    prompts = json.dumps(chat.messages)
    assert HIDDEN not in prompts and "hidden" not in prompts.lower()

    report = Report.model_validate(client.get(f"/incidents/{iid}/report").json())
    assert report.root_cause.status == "SUPPORTED" and report.patch is not None
    assert "price * pct / 100" in report.patch.diff
    suites = [(v.attempt, v.suite, v.outcome) for v in report.validation_runs]
    assert (0, "reproducer", "failed") in suites
    assert any(s[1] == "hidden" and s[2] == "passed" for s in suites)
    assert "Verified only by the lab" in report.limitations

    rv = client.post(
        f"/incidents/{iid}/review",
        json={"decision": "approve", "reviewer": "ruhan", "patch_sha256": report.patch.sha256},
    )
    assert rv.status_code == 201
    assert client.get(f"/incidents/{iid}").json()["state"] == "CLOSED"


def test_second_investigate_is_409(session_factory, tmp_path):
    repo = make_repo(tmp_path / "r", FILES)
    chat = FakeChat(resp(SUBMIT_CODE), resp(content=FIX))
    client = make_client(session_factory, FakeFactory(chat, repo))
    iid = new_incident(session_factory)
    assert client.post(f"/incidents/{iid}/investigate").status_code == 202
    assert client.post(f"/incidents/{iid}/investigate").status_code == 409  # state moved on
    other = new_incident(session_factory)
    investigation._running.add(uuid.UUID(other))  # a job for it is still running
    assert client.post(f"/incidents/{other}/investigate").status_code == 409


def test_route_status_codes(session_factory, tmp_path):
    client = make_client(session_factory, FakeFactory(FakeChat(), make_repo(tmp_path / "r", FILES)))
    assert client.post(f"/incidents/{uuid.uuid4()}/investigate").status_code == 404
    assert client.post("/incidents/not-a-uuid/investigate").status_code == 422
    with session_factory() as db:
        manual = service.create_incident(db, IncidentCreate(symptom="boom", service="shop_api"))
    assert client.post(f"/incidents/{manual.id}/investigate").status_code == 422


def test_no_provider_configured_is_503_not_a_crash(session_factory):
    client = make_client(session_factory, investigation.InvestigationFactory())
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        llm_provider="beatapi", beatapi_api_key=SecretStr(""), manifest=str(MANIFEST)
    )
    iid = new_incident(session_factory, "shop_api-001")
    r = client.post(f"/incidents/{iid}/investigate")
    assert r.status_code == 503 and "provider" in r.json()["detail"]
    assert client.get(f"/incidents/{iid}").json()["state"] == "CREATED"  # nothing started


def test_pipeline_failure_is_recorded_and_lock_released(session_factory):
    client = make_client(session_factory, FakeFactory(FakeChat(), None, fail=True))
    iid = new_incident(session_factory)
    assert client.post(f"/incidents/{iid}/investigate").status_code == 202
    assert uuid.UUID(iid) not in investigation._running
    with session_factory() as db:
        events = repository.list_events(db, uuid.UUID(iid))
    failed = [e for e in events if e.event_type == "investigation_failed"]
    assert failed and failed[0].payload["error"] == "RuntimeError"


# ---- 3. missing_evidence reaches the report from the real pipeline ------------------------------


def test_inconclusive_pipeline_run_persists_missing_evidence(session_factory, tmp_path):
    chat = FakeChat(resp(call("submit_diagnosis", cause_class="insufficient_evidence")))
    client = make_client(session_factory, FakeFactory(chat, make_repo(tmp_path / "r", FILES)))
    iid = new_incident(session_factory, "abstain")
    assert client.post(f"/incidents/{iid}/investigate").status_code == 202
    report = client.get(f"/incidents/{iid}/report").json()
    assert report["root_cause"]["status"] == "INCONCLUSIVE"
    assert report["outcome"]["missing_evidence"]
    assert all(isinstance(m, str) for m in report["outcome"]["missing_evidence"])
