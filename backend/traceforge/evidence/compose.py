"""Compose evidence: services, depends_on, env key names (values redacted unless allowlisted)."""

import hashlib
from dataclasses import dataclass

import yaml

from traceforge.evidence.config import allowed
from traceforge.evidence.model import EvidenceConfig
from traceforge.evidence.redaction import redact_value, secret_kind


@dataclass
class ComposeService:
    name: str
    line: int
    content: str


def read_compose(cfg: EvidenceConfig) -> tuple[str, str]:
    """(text with LF newlines, sha256 of that text). Newline-normalised so both laptops agree."""
    text = (cfg.repo_root / cfg.compose_file).read_text("utf-8").replace("\r\n", "\n")
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def _merge(doc: dict) -> dict[str, dict]:
    """safe_load already resolves YAML anchors/merge keys."""
    return doc.get("services") or {}


def service_items(text: str, cfg: EvidenceConfig, known_secrets=()) -> list[ComposeService]:
    doc = yaml.safe_load(text) or {}
    lines = text.splitlines()
    out = []
    for name, svc in _merge(doc).items():
        if not isinstance(svc, dict):
            continue
        env = svc.get("environment") or {}
        if isinstance(env, list):
            env = dict(e.split("=", 1) if "=" in e else (e, "") for e in env)
        dep = svc.get("depends_on") or []
        dep = sorted(dep) if isinstance(dep, (list, dict)) else []
        shown = {
            k: (
                redact_value(k, str(v), known_secrets)
                if secret_kind(k) or allowed(k, cfg.env_allowlist)
                else "«not-allowlisted»"
            )
            for k, v in sorted(env.items())
        }
        parts = [f"service {name}", f"image: {svc.get('image', '(build)')}", f"depends_on: {dep}"]
        parts.append("environment: " + ", ".join(f"{k}={v}" for k, v in shown.items()))
        if svc.get("healthcheck"):
            parts.append("healthcheck: yes")
        line = next((i + 1 for i, ln in enumerate(lines) if ln.rstrip() == f"  {name}:"), 1)
        out.append(ComposeService(name, line, "\n".join(parts)))
    return out
