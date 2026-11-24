"""Diagnosis-to-patch safeguards (pipeline v5): never patch a target the evidence cannot justify.

`validate_target` runs after diagnosis and before any patch request. It never substitutes a
different target; if the target is unusable the run abstains with a typed reason.
"""

from traceforge.agent.tools import SubmitDiagnosis, ToolContext
from traceforge.contracts.case_manifest import REPAIRABLE


def _source_text(tc: ToolContext, path: str) -> str | None:
    read = getattr(tc.ctx, "read_file", None)
    return read(tc.case, path) if read else None


def validate_target(tc: ToolContext, diag: SubmitDiagnosis | None) -> str | None:
    """None if the diagnosed target may be patched, else the failure reason."""
    if diag is None or diag.cause_class not in REPAIRABLE:
        return None
    if diag.path:
        if not tc.allowed_path(diag.path):
            return "unsupported_target: path not permitted"
        if tc.ctx.read_symbol(tc.case, diag.path, diag.qualname or "") is None:
            return "unsupported_target: symbol not found"
        return None
    if diag.config_key:
        bare = diag.config_key.rsplit(".", 1)[-1].lower()
        if not any(bare in i.content.lower() for i in tc.evidence.items):
            return "unsupported_target: config key not in evidence"
        return None
    return "unsupported_target: no location"
