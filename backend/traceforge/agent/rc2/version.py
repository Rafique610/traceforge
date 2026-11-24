"""RC2 selection, fingerprint and the guard that keeps RC2 results from being labelled RC1."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from traceforge.contracts.evidence import EvidenceBundle
from traceforge.evaluation.fingerprint import FILES as RC1_FILES
from traceforge.evaluation.fingerprint import PKG, code_fingerprint

from .rationale import tolerant_rationale
from .repeat_guard import repeat_guard

RC1_FINGERPRINT = "ee3d8d873a6e939451650d031a919799138e621859f79bdd91994af3f6456b51"
RC2_FILES = RC1_FILES + (
    "agent/rc2/__init__.py", "agent/rc2/rationale.py", "agent/rc2/repeat_guard.py",
    "agent/rc2/config_check.py", "agent/rc2/version.py",
)  # fmt: skip
DEFAULT_VERSION = "rc1"


class VersionLabelError(ValueError):
    pass


def rc2_fingerprint(root: Path = PKG) -> dict:
    return code_fingerprint(RC2_FILES, root)


def select_chat_fn(
    version: str,
    chat_fn: Callable[..., Any],
    log: list[dict[str, Any]] | None = None,
    evidence: EvidenceBundle | None = None,
) -> Callable[..., Any]:
    """rc1 (default): chat_fn unchanged (identity). rc2: tolerant rationale + repeat guard."""
    if version == "rc1":
        return chat_fn
    if version != "rc2":
        raise VersionLabelError(f"unknown pipeline version {version!r}")
    log = log if log is not None else []
    return repeat_guard(tolerant_rationale(chat_fn, log), log, evidence)


def run_label(version: str, fingerprint_sha: str) -> dict[str, str]:
    """Metadata for a run record. Refuses an RC2 run carrying the RC1 fingerprint, and an RC1 run
    whose fingerprint is not the frozen RC1 one."""
    if version == "rc1":
        if fingerprint_sha != RC1_FINGERPRINT:
            raise VersionLabelError("rc1 run must carry the frozen RC1 fingerprint")
    elif version == "rc2":
        if fingerprint_sha == RC1_FINGERPRINT:
            raise VersionLabelError("rc2 run must not carry the RC1 fingerprint")
    else:
        raise VersionLabelError(f"unknown pipeline version {version!r}")
    return {"code_version": version, "code_fingerprint": fingerprint_sha}
