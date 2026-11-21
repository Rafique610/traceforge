"""Effective config evidence: allowlisted env of the container + declared settings fields."""

import ast
import fnmatch
from collections.abc import Iterable

from traceforge.evidence.model import EvidenceConfig
from traceforge.evidence.redaction import redact_value, secret_kind


def allowed(key: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(key.upper(), p.upper()) for p in patterns)


def effective_env(
    env: dict[str, str], cfg: EvidenceConfig, known_secrets: Iterable[str] = ()
) -> list[tuple[str, str]]:
    """(key, redacted value) for allowlisted keys, sorted. Secret-like keys that are allowlisted
    by pattern are still redacted; non-allowlisted keys are not emitted at all."""
    return [
        (k, redact_value(k, v, known_secrets))
        for k, v in sorted(env.items())
        if allowed(k, cfg.env_allowlist)
    ]


def declared_settings(source: str) -> list[tuple[str, str, int]]:
    """(field, "annotation = default", line) of Settings class fields, read statically."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    out = []
    for cls in (
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name.endswith("Settings")
    ):
        for n in cls.body:
            if (
                isinstance(n, ast.AnnAssign)
                and isinstance(n.target, ast.Name)
                and n.target.id != "model_config"
            ):
                text = f"[{ast.unparse(n.annotation)}]"
                if n.value is not None:
                    text += " = " + (
                        "<redacted>" if secret_kind(n.target.id) else ast.unparse(n.value)
                    )
                out.append((n.target.id, text, n.lineno))
    return out


def find_settings_file(cfg: EvidenceConfig, service: str) -> str | None:
    """Repo-relative POSIX path of the service's settings.py (first match), else None."""
    base = cfg.repo_root / "lab" / service
    for p in sorted(base.rglob("settings.py")):
        if "tests" not in p.parts:
            return p.relative_to(cfg.repo_root).as_posix()
    return None
