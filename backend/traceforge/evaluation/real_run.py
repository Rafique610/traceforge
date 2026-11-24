"""Real-sources run function for the experiment runner (frozen-split runs).

One case = one faulty git repo built from the COMMITTED case data (no dataset regeneration), saved
evidence, real retrieval, the repair loop in the Docker sandbox with hidden tests mounted read-only
by the sandbox only, and every model prompt screened by the hidden-test leak guard. Every run writes
its artifacts immediately under `<run_dir>/cases/<case>.r<k>/`; hidden-test names and outputs are
never written (only pass/fail counts).
"""

import hashlib
import json
import subprocess
import time
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from traceforge.agent import gateway
from traceforge.agent.e2e import allowlist, build_repo, rm_tree, slug, visible_sources
from traceforge.agent.lab_collect import SCRATCH
from traceforge.agent.persist import RunLog
from traceforge.agent.real_sources import HiddenLeakGuard, make_sandbox_run_tests, real_sources
from traceforge.agent.repair_run import run_case_with_repair
from traceforge.config import Settings
from traceforge.contracts.agent_run import AgentRunRecord
from traceforge.contracts.case_manifest import CaseManifest
from traceforge.evaluation.errors import StopRun
from traceforge.evaluation.fingerprint import code_fingerprint
from traceforge.repair.diffstats import diff_stats
from traceforge.repair.loop import sha256_text

OFFICIAL = ("axforge", "glm-5.3-flash")


def tier_for(provider: str, model: str) -> str:
    """Official results come only from AxForge glm-5.3-flash; anything else is development."""
    return "official" if (provider, model) == OFFICIAL else "development"


def git_state(cwd: Path | None = None) -> dict:
    def run(*args: str) -> str:
        p = subprocess.run(["git", *args], capture_output=True, text=True, timeout=20, cwd=cwd)  # noqa: S603,S607
        return p.stdout.strip()

    try:
        return {"git_sha": run("rev-parse", "HEAD"), "dirty": bool(run("status", "--porcelain"))}
    except (OSError, subprocess.SubprocessError):
        return {"git_sha": "unknown", "dirty": None}


class Timer:
    """Accumulates wall seconds and call counts for one phase (thread-confined: one per run)."""

    def __init__(self) -> None:
        self.seconds, self.calls = 0.0, 0

    def wrap(self, fn):
        def timed(*a, **k):
            t = time.monotonic()
            try:
                return fn(*a, **k)
            finally:
                self.seconds += time.monotonic() - t
                self.calls += 1

        return timed


class MissingInputs(RuntimeError):
    """A case cannot run yet (no saved evidence bundle); skipped without writing a record."""


def request_recorder(chat_fn, log: list[dict]):
    """Record every model request of one case: stage, attempt index, a hash of the exact messages,
    whether the prompt carries visible-test feedback (and that payload), and the cache decision."""

    def recorded(messages, tools=None, **kw):
        row = {
            "n": len(log) + 1,
            "stage": "diagnose" if tools else "patch",
            "attempt_index": kw.get("attempt_index", 0),
            "messages_sha256": hashlib.sha256(
                json.dumps(messages, sort_keys=True).encode()
            ).hexdigest(),
        }
        text = "\n".join(str(m.get("content")) for m in messages)
        a, b = text.find("<visible_test_feedback>"), text.find("</visible_test_feedback>")
        row["has_feedback"] = a >= 0
        if a >= 0:
            row["feedback"] = text[a + len("<visible_test_feedback>") : b].strip()
        log.append(row)
        try:
            resp = chat_fn(messages, tools, **kw)
        except Exception as e:
            row["error"] = type(e).__name__
            raise
        row.update(cache_hit=resp.cache_hit, tokens_in=resp.tokens_in, tokens_out=resp.tokens_out)
        return resp

    return recorded


def components(pipeline: str) -> dict:
    """What changed relative to the formal pipeline, so each component can be evaluated apart."""
    if pipeline == "v4":
        return {}
    return {
        "config_id": "dev-d1",
        "cache": "disabled: every request is live, nothing is read from or written to the cache",
        "symptom_in_diagnose_prompt": "baseline visible reproducer + visible suite output",
        "evidence_labels": "scope, basis, origin, path:line shown; static never labelled runtime",
        "lexical_query": "symptom terms (endpoint, test names, assertion identifiers)",
        "graph_anchors": "failing visible tests -> tests_covers -> covered code; routes",
        "diagnosis_schema": "SubmitDiagnosisV2 (symptom, reconciliation, confidence, sufficiency)",
        "claim_validation": "symptom cited, key/symbol exist, evidence mentions target",
        "tool_budget": "8 valid calls; rejected calls do not count (cap 3); typed failure reasons",
        "discovery": "workspace_files index in prompt + search_code tool + suggestions",
        "handoff": "validate_target before patch; patch scope policy (edit only the target)",
        "prompts": "diagnose_v2 + patch_v5",
    }


def failure_category(rec: AgentRunRecord) -> str:
    if rec.failure_reason and rec.failure_reason.startswith("pipeline_crash"):
        return "pipeline_crash"
    if rec.outcome == "TEST_VERIFIED_IN_LAB":
        return "none"
    if rec.diagnosis.abstained:
        return "abstained" if not rec.failure_reason else f"abstained:{rec.failure_reason}"
    return rec.failure_reason or rec.outcome.lower()


def make_real_run_fn(
    manifest: Path,
    evidence_dir: Path,
    run_dir: Path,
    provider: str,
    model: str,
    settings: Settings | None = None,
    pipeline: str = "v4",
    diagnose_only: bool = False,
    patch_from: Path | None = None,
    frozen: Path | None = None,
    share_diagnosis: bool = False,
    final_rc1: bool = False,
):
    """Return `run_fn(case, condition, replicate) -> AgentRunRecord` with a `.ready(case)` check.

    `pipeline` v4 = the formal pipeline (unchanged). v5 = the development track: the symptom from
    the base-commit visible tests, labelled evidence, a validated diagnosis. v5 runs are always
    tier "development", whatever the provider, and never official.
    """
    manifest, evidence_dir, run_dir = manifest.resolve(), evidence_dir.resolve(), run_dir.resolve()
    datasets = manifest.parents[1]  # absolute: the sandbox rejects relative dataset paths
    s = settings or Settings(llm_provider=provider, llm_model=model)
    tier = (
        "final-rc1"
        if final_rc1
        else (tier_for(provider, model) if pipeline == "v4" else "development")
    )
    patch_from = patch_from.resolve() if patch_from else None
    repo_root = datasets.parent

    def load_saved(case: CaseManifest, condition: str, replicate: int):
        """Saved diagnosis and the exact evidence it was made on (patch stage: nothing is
        regenerated). The files are checked against the frozen manifest first."""
        from traceforge.agent.tools import SubmitDiagnosisV2
        from traceforge.contracts.evidence import EvidenceBundle
        from traceforge.evaluation import freeze_manifest as fm

        d = patch_from / "cases" / f"{case.case_id}.r{replicate}"
        rec_path = patch_from / "records" / f"{case.case_id}.r{replicate}.json"
        need = [d / "diagnosis.json", d / "evidence_v5.json", rec_path]
        if frozen is not None:
            problems = fm.verify_files(json.loads(frozen.read_text("utf-8")), need, repo_root)
            if problems:
                raise MissingInputs(f"frozen diagnosis files not intact: {problems}")
        rec = json.loads(rec_path.read_text("utf-8"))
        same = rec["condition"] == condition or (
            share_diagnosis and rec["condition"][0] == condition[0]  # same retrieval arm
        )
        if not same or rec["pipeline_version"] != "v5":
            raise MissingInputs(f"saved diagnosis is {rec['condition']}/{rec['pipeline_version']}")
        text = (d / "diagnosis.json").read_text("utf-8").strip()
        # the source run produced no submission (abstained after budget/invalid output): a shared
        # diagnosis is then the same abstention, reproduced without any model call
        none = text == "null"
        sub = (
            SubmitDiagnosisV2(cause_class="insufficient_evidence")
            if none
            else SubmitDiagnosisV2.model_validate_json(text)
        )
        if sub.cause_class == "insufficient_evidence" and not share_diagnosis:
            raise MissingInputs("the saved diagnosis abstained: there is nothing to patch")
        ev = EvidenceBundle.model_validate_json((d / "evidence_v5.json").read_text("utf-8"))
        source = {
            "run": patch_from.name,
            "diagnosis_sha256": fm._sha(d / "diagnosis.json"),
            "evidence_sha256": fm._sha(d / "evidence_v5.json"),
            "frozen_manifest": frozen.name if frozen else None,
            "diagnosis_condition": rec["condition"],
            "shared_diagnosis": rec["condition"] != condition,
            "source_failure_reason": rec.get("failure_reason") if none else None,
        }
        return sub, ev, source

    def ready(case: CaseManifest) -> None:
        if not (evidence_dir / f"{case.case_id}.json").is_file():
            raise MissingInputs(f"no evidence bundle for {case.case_id} in {evidence_dir}")

    def run_fn(case: CaseManifest, condition: str, replicate: int) -> AgentRunRecord:
        ready(case)
        from traceforge.agent import symptoms  # deterministic symptom text from the case's own data

        # v4 keeps its original hash-only symptom string. v5 builds the real symptom later from
        # the visible tests and never calls symptom_for (which reads gold terms).
        symptom = symptoms.symptom_for(case, datasets) if pipeline == "v4" else ""
        tag = f"{slug(run_dir.name)}-{case.case_id}-r{replicate}"
        repo_dir = SCRATCH / "repos" / tag
        rm_tree(repo_dir)
        try:
            t_start = time.monotonic()
            repo, head = build_repo(case, datasets, repo_dir)
            src = real_sources(manifest, evidence_dir, repo)
            guard = HiddenLeakGuard(
                datasets / "hidden_tests",
                [case.case_id],
                [repo / "lab" / case.service / "tests", datasets / "reproducers" / case.case_id],
            )
            model_t, sandbox_t = Timer(), Timer()
            chat = guard.wrap(
                partial(
                    gateway.chat,
                    settings=s,
                    replicate_index=replicate,
                    seed=0,
                    temperature=0.0,
                    use_cache=(pipeline == "v4"),  # dev-d1: every request is a live request
                )
            )
            reqlog: list[dict] = []
            chat = model_t.wrap(request_recorder(chat, reqlog))
            runlog = RunLog(sandbox_t.wrap(make_sandbox_run_tests(repo, datasets, case.service)))
            sym_obj = saved = baseline_visible = patch_source = None
            if patch_from is not None:  # patch stage: saved diagnosis, no symptom/diagnose request
                from traceforge.contracts.test_run import TestRunRequest
                from traceforge.repair.worktree import worktree

                sub, ev, patch_source = load_saved(case, condition, replicate)
                saved = (sub, ev, patch_source.get("source_failure_reason"))
                with worktree(str(repo), head) as wt:  # baseline visible outcomes (no model)
                    base = runlog(
                        TestRunRequest(case_id=case.case_id, worktree_path=str(wt), suite="visible")
                    )
                baseline_visible = {t.id: t.outcome for t in base.tests}
            elif pipeline == "v5":
                from traceforge.agent import symptom as symptom_mod
                from traceforge.repair.worktree import worktree

                with worktree(str(repo), head) as wt:
                    sym_obj = symptom_mod.collect_symptom(runlog, str(wt), case.case_id)
                if (why := symptom_mod.validate(sym_obj, guard.check)) and sym_obj.status == "ok":
                    sym_obj.status = f"blocked: {why[0]}"  # fail closed: nothing enters a prompt
                symptom = "\n".join(sym_obj.texts())
            prep_s = time.monotonic() - t_start
            art: dict = {"requests": reqlog}
            t0 = datetime.now(UTC)
            rec = run_case_with_repair(
                case, condition, src, repo_path=str(repo), base_sha=head, run_tests=runlog,
                allowlist=allowlist(repo, case.service),
                visible_test_sources=visible_sources(repo, datasets, case),
                settings=s, chat_fn=chat, replicate=replicate,
                dataset_sha256=src.cases.sha256, artifacts=art,
                pipeline=pipeline, symptom=sym_obj, diagnose_only=diagnose_only, saved=saved,
            )  # fmt: skip
            art["patch_source"], art["baseline_visible"] = patch_source, baseline_visible
            if pipeline == "v5":  # retrieval record: L, G and their union (no gold, no model)
                from traceforge.retrieval.compare import compare

                art["sym_obj"] = sym_obj
                if art.get("evidence") is not None:
                    art["retrieval"] = compare(art["evidence"], src.context.retrieve, 3000)
            t1 = datetime.now(UTC)
            total_s = time.monotonic() - t_start
            timings = {
                "total_s": round(total_s, 2), "prepare_s": round(prep_s, 2),
                "model_s": round(model_t.seconds, 2), "model_calls": model_t.calls,
                "sandbox_s": round(sandbox_t.seconds, 2), "sandbox_runs": sandbox_t.calls,
                "other_s": round(total_s - prep_s - model_t.seconds - sandbox_t.seconds, 2),
            }  # fmt: skip
        finally:
            rm_tree(repo_dir)
        if rec.failure_reason and rec.failure_reason.startswith("provider_error"):
            # An outage is not a result: keep the artifacts, write no AgentRunRecord and stop the
            # run so a rerun with the same run id repeats this case.
            tagged = f"{replicate}.provider_error.{int(t0.timestamp())}"
            _save_artifacts(run_dir, case, tagged, rec, art, guard, tier, provider, model,
                            symptom, evidence_dir, t0, t1, head, runlog, timings)  # fmt: skip
            raise StopRun(rec.failure_reason)
        _save_artifacts(run_dir, case, replicate, rec, art, guard, tier, provider, model, symptom,
                        evidence_dir, t0, t1, head, runlog, timings)  # fmt: skip
        return rec

    run_fn.ready = ready  # type: ignore[attr-defined]
    run_fn.load_saved = load_saved  # type: ignore[attr-defined]
    run_fn.datasets = datasets  # type: ignore[attr-defined]
    return run_fn


def _save_artifacts(run_dir, case, replicate, rec, art, guard, tier, provider, model, symptom,
                    evidence_dir, t0, t1, head, runlog=None, timings=None) -> None:  # fmt: skip
    d = run_dir / "cases" / f"{case.case_id}.r{replicate}"  # replicate may carry a suffix
    d.mkdir(parents=True, exist_ok=True)
    rr = art.get("repair")
    diff = art.get("diff") or ""
    sub = art.get("submitted")
    (d / "patch.diff").write_text(diff, "utf-8")
    (d / "requests.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in art.get("requests") or []), "utf-8"
    )
    (d / "diagnosis.json").write_text(sub.model_dump_json(indent=2) if sub else "null", "utf-8")
    (d / "trace.json").write_text(json.dumps(art.get("trace"), indent=2), "utf-8")
    if art.get("sym_obj") is not None:  # v5 only: every symptom detail with its provenance
        so = art["sym_obj"]
        (d / "symptom.json").write_text(json.dumps(so.as_dict(), indent=2), "utf-8")
        (d / "evidence_v5.json").write_text(art["evidence"].model_dump_json(indent=1), "utf-8")
        (d / "retrieval.json").write_text(json.dumps(art.get("retrieval"), indent=1), "utf-8")
        if art.get("context") is not None:  # exactly which chunks were rendered into the prompt
            from traceforge.agent import prompting

            sent = prompting.rendered_hits(art["context"], prompting.DEFAULT_CONTEXT_BUDGET_CHARS)
            (d / "context_sent.json").write_text(json.dumps({
                "arm": rec.condition[0], "n_retrieved": len(art["context"].hits),
                "n_rendered": len(sent), "rendered_chars": sum(len(b) for _h, b in sent),
                "hits": [{"id": h.node_id, "path": h.path, "lines": [h.start_line, h.end_line],
                          "score": round(h.score, 4), "reasons": h.reasons[:4]}
                         for h, _b in sent],
            }, indent=1), "utf-8")  # fmt: skip
    for x in rr.attempts if rr else []:  # every attempt's patch, not only the final one
        if x.diff:
            (d / f"attempt{x.n}.diff").write_text(x.diff, "utf-8")
    if art.get("baseline_visible") is not None:  # patch stage: visible outcomes before any patch
        bv = json.dumps(art["baseline_visible"], indent=1)
        (d / "baseline_visible.json").write_text(bv, "utf-8")
    hidden = rr.hidden_result if rr else None
    (d / "repair.json").write_text(json.dumps({
        "outcome": rr.outcome if rr else None, "reason": rr.reason if rr else None,
        "attempts": [{"n": x.n, "reasons": x.reasons, "visible_passed": x.visible_passed,
                      "has_diff": x.diff is not None, "counts": x.counts,
                      "feedback_items": [fi.provenance() for fi in x.feedback_items],
                      "feedback_sha256": x.feedback_sha256, "edit_summary": x.edit_summary,
                      "rejection_text": x.rejection_text, "sandbox_detail": x.sandbox_detail,
                      "visible_outcomes": x.visible_outcomes,
                      "reproducer_outcomes": x.reproducer_outcomes,
                      "diff_stats": diff_stats(x.diff) if x.diff else None,
                      "diff_sha256": sha256_text(x.diff) if x.diff else None,
                      "feedback_received": x.feedback,  # visible-test output only; never hidden
                      } for x in rr.attempts] if rr else [],
        "hidden_passed": rr.hidden_passed if rr else None,
        "hidden_counts": {"passed": hidden.passed, "failed": hidden.failed} if hidden else None,
        "signature_changed": rr.signature_changed if rr else None,
    }, indent=2), "utf-8")  # fmt: skip
    ev = (evidence_dir / f"{case.case_id}.json").read_bytes()
    meta = {
        "tier": tier, "provider": provider, "model": model, "case_id": case.case_id,
        "replicate": replicate, "condition": rec.condition, "started_at": t0.isoformat(),
        "finished_at": t1.isoformat(), "evidence_sha256": hashlib.sha256(ev).hexdigest(),
        "symptom_sha256": hashlib.sha256(symptom.encode()).hexdigest(),
        "patch_sha256": rec.patch_sha256, "repair_repo_head": head,
        "failure_category": failure_category(rec), "diagnosis_correct_class":
        rec.diagnosis.cause_class == case.cause_class, "hidden_guard_calls": guard.calls,
        "hidden_fragment_hits": len(guard.fragment_hits),
        "tokens_in": rec.tokens_in, "tokens_out": rec.tokens_out, "latency_ms": rec.latency_ms,
        "attempts": rec.attempts,
        "stage": "patch" if art.get("patch_source") else "diagnosis",
        "patch_source": art.get("patch_source"),
        "pipeline_version": rec.pipeline_version,
        "code_fingerprint": code_fingerprint() if rec.pipeline_version == "v5" else None,
        "pipeline_components": components(rec.pipeline_version),
        "symptom_status": art["sym_obj"].status if art.get("sym_obj") is not None else None,
        "diagnosis_rejected_calls": art.get("diagnosis_rejected"),
        "timings": timings,
        "sandbox_errors": [(suite, (r.error or "timed out")[:300]) for suite, r in
                           (runlog.calls if runlog else []) if r.error or r.timed_out],
        **git_state(),
    }  # fmt: skip
    (d / "run_meta.json").write_text(json.dumps(meta, indent=2), "utf-8")
