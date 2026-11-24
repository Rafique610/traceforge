"""run_case_with_repair: diagnosis -> patch requests -> repair loop -> AgentRunRecord."""

from sqlalchemy.orm import Session

from traceforge.agent.diagnose import ChatFn, Usage
from traceforge.agent.gateway import GatewayError, OutputTruncated
from traceforge.agent.patch import ask_patch
from traceforge.agent.pipeline import Sources, run_case
from traceforge.agent.tools import SubmitDiagnosis, ToolContext
from traceforge.config import Settings
from traceforge.contracts.agent_run import AgentRunRecord
from traceforge.contracts.case_manifest import CaseManifest
from traceforge.incidents.models import Incident
from traceforge.repair import RepairResult, run_repair
from traceforge.repair.scope import make_scope_check


def run_case_with_repair(
    case: CaseManifest | Incident,
    condition: str,
    sources: Sources | None = None,
    *,
    repo_path: str,
    base_sha: str,
    run_tests,
    allowlist,
    visible_test_sources=(),
    db: Session | None = None,
    settings: Settings | None = None,
    chat_fn: ChatFn | None = None,
    replicate: int = 0,
    dataset_sha256: str | None = None,
    artifacts: dict | None = None,
    pipeline: str = "v4",
    symptom=None,
    diagnose_only: bool = False,
    saved=None,
) -> AgentRunRecord:
    """Condition L0/G0/L1/G1 = L|G retrieval, 0|1 = F0|F1. Abstain/runtime_dependency: none."""
    err: list[str] = []
    asked = [0]  # patch requests made so far in this case: the attempt index (0 = first)

    def repair(tc: ToolContext, diag: SubmitDiagnosis, chat: ChatFn, usage: Usage) -> RepairResult:
        def propose(_ctx, feedback: str | None) -> str:
            k, asked[0] = asked[0], asked[0] + 1
            try:  # F0 passes feedback=None every attempt; F1 passes the visible output
                return ask_patch(tc, diag, chat, usage, feedback, k) or ""
            except OutputTruncated:  # the model ran out of output tokens: a result, not an outage
                err.append("output_truncated")
                return ""
            except GatewayError as e:
                err.append(f"provider_error: {e}")
                return ""

        rr = run_repair(
            case_id=tc.case.case_id,
            repo_path=repo_path,
            base_sha=base_sha,
            condition="F" + condition[1],  # type: ignore[arg-type]
            context=None,
            propose_edit=propose,
            run_tests=run_tests,
            allowlist=allowlist,
            visible_test_sources=visible_test_sources,
            scope_check=make_scope_check(diag) if pipeline == "v5" else None,
            feedback_style="v5" if pipeline == "v5" else "legacy",
        )
        if artifacts is not None:
            artifacts["repair"] = rr  # RepairResult (incl. hidden_result), for persistence
        if err and rr.outcome == "NO_PATCH":
            rr.reason = err[-1]
        return rr

    return run_case(
        case,
        condition,
        sources,
        db=db,
        settings=settings,
        chat_fn=chat_fn,
        replicate=replicate,
        dataset_sha256=dataset_sha256,
        repair=repair,
        artifacts=artifacts,
        pipeline=pipeline,
        symptom=symptom,
        diagnose_only=diagnose_only,
        saved=saved,
    )
