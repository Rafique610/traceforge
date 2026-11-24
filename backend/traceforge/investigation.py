"""POST /incidents/{id}/investigate: run the agent pipeline + repair loop in a background task.

The route answers 202 at once; the frontend polls GET /incidents/{id} for the state changes the
pipeline writes (SNAPSHOT_LOCKED ... DIAGNOSED -> PATCH_PROPOSED -> VALIDATING ->
VERIFIED/UNVERIFIED -> REVIEW_PENDING, or INCONCLUSIVE -> REVIEW_PENDING). Gateway, case source
and sandbox come from an injectable `InvestigationFactory` (override `get_factory` in tests);
the default one builds them from Settings and answers 503 when no provider/manifest is
configured. Hidden tests, max attempts and isolation are those of agent/repair_run.py and are
not changed here."""

import hashlib
import json
import logging
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session, sessionmaker

from traceforge import database
from traceforge.agent.persist import RunLog, record_missing_evidence, save_outcome
from traceforge.agent.pipeline import Sources
from traceforge.agent.repair_run import run_case_with_repair
from traceforge.config import Settings, get_settings
from traceforge.contracts.case_manifest import REPAIRABLE
from traceforge.database import get_db
from traceforge.incidents import repository
from traceforge.incidents.models import AuditEvent, Incident
from traceforge.incidents.states import State

log = logging.getLogger(__name__)
router = APIRouter(prefix="/incidents", tags=["investigation"])

_running: set[uuid.UUID] = set()
_lock = threading.Lock()


@dataclass
class Plan:
    """Everything one investigation needs; built per incident by the factory."""

    sources: Sources
    chat_fn: Callable[..., Any]
    run_tests: Callable[..., Any]
    repo_path: str
    base_sha: str
    allowlist: list[str]
    visible_test_sources: list[str] = field(default_factory=list)
    condition: str = "G1"
    pipeline: str = "v4"
    symptom: Any = None
    settings: Settings | None = None
    dataset_sha256: str | None = None
    cleanup: Callable[[], None] | None = None


class _SymptomPersistingEvidence:
    """Evidence source that stores the bundle INCLUDING the v5 symptom items before the pipeline
    runs. The pipeline stores the raw bundle and appends symptom items afterwards, so a diagnosis
    citing one of those items failed the DIAGNOSED guard ("ids not stored"). The appended items
    are deterministic (`with_symptom`), so the pipeline's own bundle matches what is stored."""

    def __init__(self, inner: Any, db: Session, symptom: Any):
        self.inner, self.db, self.symptom = inner, db, symptom

    def collect(self, incident_id: str, service: str, case: Any):
        bundle = self.inner.collect(incident_id, service, case)
        if self.symptom is not None and self.symptom.status in ("ok", "no_failure"):
            from traceforge.agent.symptom import with_symptom

            if not repository.list_evidence(self.db, uuid.UUID(incident_id)):
                repository.save_evidence_bundle(self.db, with_symptom(bundle, self.symptom))
                self.db.commit()
        return bundle

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


def provider_ready(s: Settings) -> bool:
    """True when the configured provider can be called (a key is set; ollama needs none).
    Only presence is checked: key values are never read out or logged."""
    p = s.llm_provider
    if p == "ollama":
        return True
    if p == "axforge":
        key = s.axforge_api_key2 if s.axforge_key_slot == "2" else s.axforge_api_key
    else:
        key = getattr(s, f"{p}_api_key")
    return bool(key.get_secret_value())


class InvestigationFactory:
    """Default factory: real provider gateway, manifest case source, saved evidence, sandbox."""

    def check(self, settings: Settings, incident: Incident) -> None:
        """Raise HTTPException (503/422) when this incident cannot be investigated here."""
        if not provider_ready(settings):
            raise HTTPException(
                503,
                f"no LLM provider is configured (provider '{settings.llm_provider}' has no "
                "credentials); set TRACEFORGE_LLM_PROVIDER and its key, then retry",
            )
        if not settings.manifest:
            raise HTTPException(503, "no case source is configured (set TRACEFORGE_MANIFEST)")
        from traceforge.agent.real_sources import ManifestCaseSource

        try:
            ManifestCaseSource(settings.manifest).get(incident.case_id)
        except (KeyError, OSError, ValueError):
            raise HTTPException(
                422, f"case {incident.case_id!r} is not in the configured manifest"
            ) from None

    def build(self, settings: Settings, incident: Incident) -> Plan:  # pragma: no cover (live)
        from functools import partial
        from pathlib import Path

        from traceforge.agent import gateway
        from traceforge.agent import symptom as symptom_mod
        from traceforge.agent.e2e import allowlist, build_repo, rm_tree, visible_sources
        from traceforge.agent.lab_collect import SCRATCH
        from traceforge.agent.real_sources import (
            HiddenLeakGuard,
            ManifestCaseSource,
            make_sandbox_run_tests,
            real_sources,
        )
        from traceforge.repair.worktree import worktree

        manifest = Path(settings.manifest)
        datasets = settings.datasets_dir or manifest.parents[1]
        case = ManifestCaseSource(manifest).get(incident.case_id)
        repo_dir = SCRATCH / "repos" / f"inv-{incident.id}"
        rm_tree(repo_dir)
        repo, head = build_repo(case, datasets, repo_dir)
        src = real_sources(manifest, settings.evidence_dir, repo)
        guard = HiddenLeakGuard(
            datasets / "hidden_tests",
            [case.case_id],
            [repo / "lab" / case.service / "tests", datasets / "reproducers" / case.case_id],
        )
        v5 = settings.investigate_pipeline == "v5"
        chat = guard.wrap(
            partial(gateway.chat, settings=settings, replicate_index=0, seed=0,
                    temperature=0.0, use_cache=not v5)
        )  # fmt: skip
        run_tests = make_sandbox_run_tests(repo, datasets, case.service)
        sym = None
        if v5:
            with worktree(str(repo), head) as wt:
                sym = symptom_mod.collect_symptom(run_tests, str(wt), case.case_id)
            if (why := symptom_mod.validate(sym, guard.check)) and sym.status == "ok":
                sym.status = f"blocked: {why[0]}"
        return Plan(
            sources=src, chat_fn=chat, run_tests=run_tests, repo_path=str(repo), base_sha=head,
            allowlist=allowlist(repo, case.service),
            visible_test_sources=visible_sources(repo, datasets, case),
            condition=settings.investigate_condition, pipeline=settings.investigate_pipeline,
            symptom=sym, settings=settings, dataset_sha256=src.cases.sha256,
            cleanup=lambda: rm_tree(repo_dir),
        )  # fmt: skip


def get_factory() -> InvestigationFactory:
    return InvestigationFactory()


def get_session_factory() -> sessionmaker:
    return database.SessionLocal


def _fail(sf: sessionmaker, incident_id: uuid.UUID, exc: Exception) -> None:
    payload = {"error": type(exc).__name__, "message": str(exc)[:300]}
    try:
        with sf() as db:
            inc = repository.get_incident(db, incident_id)
            repository.add_event(
                db,
                AuditEvent(
                    incident_id=incident_id, actor="system", event_type="investigation_failed",
                    from_state=inc.state if inc else None, to_state=None, payload=payload,
                    payload_sha256=hashlib.sha256(json.dumps(payload).encode()).hexdigest(),
                ),
            )  # fmt: skip
            db.commit()
    except Exception:  # pragma: no cover
        log.exception("could not record investigation failure")


def investigate(
    sf: sessionmaker, factory: InvestigationFactory, settings: Settings, incident_id: uuid.UUID
) -> None:
    """The background job: never raises; a failure becomes an `investigation_failed` event."""
    plan: Plan | None = None
    try:
        with sf() as db:
            inc = repository.get_incident(db, incident_id)
            plan = factory.build(settings, inc)
            case = plan.sources.cases.get(inc.case_id)
            if plan.pipeline == "v5":
                plan.sources.evidence = _SymptomPersistingEvidence(
                    plan.sources.evidence, db, plan.symptom
                )
            runlog, artifacts = RunLog(plan.run_tests), {}
            rec = run_case_with_repair(
                inc, plan.condition, plan.sources, repo_path=plan.repo_path,
                base_sha=plan.base_sha, run_tests=runlog, allowlist=plan.allowlist,
                visible_test_sources=plan.visible_test_sources, db=db,
                settings=plan.settings or settings, chat_fn=plan.chat_fn,
                dataset_sha256=plan.dataset_sha256, artifacts=artifacts,
                pipeline=plan.pipeline, symptom=plan.symptom,
            )  # fmt: skip
            graph = getattr(plan.sources.context, "graph", None)
            save_outcome(
                db, inc, cause_class=rec.diagnosis.cause_class, base_sha=case.base_sha,
                rr=artifacts.get("repair"), runlog=runlog,
                graph=graph if case.cause_class in REPAIRABLE else None,
            )  # fmt: skip
            db.refresh(inc)
            if (
                inc.state is State.REVIEW_PENDING
                and rec.diagnosis.cause_class == "insufficient_evidence"
            ):
                record_missing_evidence(db, inc, artifacts.get("evidence"), rec.failure_reason)
    except Exception as exc:
        log.exception("investigation of %s failed", incident_id)
        _fail(sf, incident_id, exc)
    finally:
        if plan is not None and plan.cleanup:
            try:
                plan.cleanup()
            except Exception:  # pragma: no cover
                log.exception("investigation cleanup failed")
        with _lock:
            _running.discard(incident_id)


@router.post("/{incident_id}/investigate", status_code=202)
def start_investigation(
    incident_id: uuid.UUID,
    background: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    factory: Annotated[InvestigationFactory, Depends(get_factory)],
    sf: Annotated[sessionmaker, Depends(get_session_factory)],
):
    inc = repository.get_incident(db, incident_id)
    if inc is None:
        raise HTTPException(404, "incident not found")
    if not inc.case_id:
        raise HTTPException(422, "only incidents with a case_id can be investigated")
    if inc.state is not State.CREATED:
        raise HTTPException(409, f"incident is {inc.state}; only CREATED incidents can start")
    factory.check(settings, inc)  # 503 / 422 before anything starts
    db.rollback()  # end the read transaction: the background job uses its own session
    with _lock:
        if incident_id in _running:
            raise HTTPException(409, "investigation already running for this incident")
        _running.add(incident_id)
    background.add_task(investigate, sf, factory, settings, incident_id)
    return {"status": "started", "incident_id": str(incident_id)}
