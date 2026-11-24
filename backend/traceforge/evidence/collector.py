"""Builds the EvidenceBundle. Redaction happens on every text BEFORE it is hashed or stored."""

import ast
import hashlib
import http.client
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from traceforge.contracts.case_manifest import CaseManifest
from traceforge.contracts.evidence import EvidenceBundle, EvidenceItem
from traceforge.evidence import compose as compose_mod
from traceforge.evidence import config as config_mod
from traceforge.evidence import docker_read, logs
from traceforge.evidence.model import EvidenceConfig
from traceforge.evidence.pathmap import to_repo_path
from traceforge.evidence.redaction import redact_text, secret_values
from traceforge.evidence.traces import Frame


@dataclass
class Collection:
    bundle: EvidenceBundle
    log_format: logs.LogFormat
    warnings: list[str] = field(default_factory=list)


def git_head(cfg: EvidenceConfig) -> str:
    out = subprocess.run(  # noqa: S603  fixed argv, no shell
        ["git", "-C", str(cfg.repo_root), "rev-parse", "HEAD"],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=10,
    )
    sha = out.stdout.strip()
    if out.returncode != 0 or len(sha) != 40:
        raise RuntimeError("cannot determine base_sha: not a git checkout")
    return sha


# Provenance labels (pipeline v5): what each kind of item is, so a static declaration is never
# presented as an observed runtime value.
_OBS_DOCKER = {
    "scope": "runtime",
    "basis": "observed",
    "origin": "docker inspect (container state)",
}
_OBS_PROBE = {
    "scope": "runtime",
    "basis": "observed",
    "origin": "HTTP probe of the running service",
}
_OBS_ENV = {
    "scope": "runtime",
    "basis": "observed",
    "origin": "container environment at start (docker inspect); not the app's Settings object",
}
_DECLARED_SRC = {
    "scope": "static",
    "basis": "declared",
    "origin": "default declared in the settings source (not a runtime value)",
}
_DECLARED_COMPOSE = {
    "scope": "static",
    "basis": "declared",
    "origin": "compose file service definition (declared, not verified as effective)",
}


class _Items:
    def __init__(self, secrets: set[str]) -> None:
        self.items: list[EvidenceItem] = []
        self.secrets = secrets

    def add(self, kind: str, service: str, content: str, **kw: Any) -> None:
        content = redact_text(content, self.secrets)
        self.items.append(
            EvidenceItem(
                id=f"EV-{len(self.items) + 1:04d}",
                kind=kind,  # type: ignore[arg-type]
                service=service,
                content=content,
                sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                **kw,
            )
        )


def _probe(url: str, timeout: float) -> str:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310  GET to a configured lab URL
            return f"GET {url} -> {r.status} {r.read(2048).decode('utf-8', 'replace')}"
    except urllib.error.HTTPError as e:
        return f"GET {url} -> {e.code} {e.read(2048).decode('utf-8', 'replace')}"
    except (OSError, http.client.HTTPException, ValueError) as e:  # timeouts, resets, bad replies
        return f"GET {url} -> unreachable ({type(e).__name__})"


def _health_text(info: docker_read.ContainerInfo) -> str:
    h = f" (health: {info.health})" if info.health else ""
    s = f"container {info.name}: {info.status}{h}, restart_count={info.restart_count}"
    if info.exit_code is not None:
        s += f", exit_code={info.exit_code}"
    return s + (f", started_at={info.started_at}" if info.started_at else "")


class EvidenceCollector:
    def __init__(self, cfg: EvidenceConfig | None = None, client: Any = None) -> None:
        self.cfg = cfg or EvidenceConfig()
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = docker_read.connect(self.cfg)
        return self._client

    def collect(self, incident_id: str, service: str, case: CaseManifest | None) -> EvidenceBundle:
        """EvidenceSource-compatible entry point (agent/sources.py)."""
        return self.collect_detailed(incident_id, service, case).bundle

    def collect_detailed(
        self, incident_id: str, service: str, case: CaseManifest | None
    ) -> Collection:
        cfg, warnings = self.cfg, []
        text, compose_sha = compose_mod.read_compose(cfg)
        names = [s.name for s in compose_mod.service_items(text, cfg)]
        if service not in names:
            raise ValueError(f"unknown service {service!r}; compose has {names}")
        infos: dict[str, docker_read.ContainerInfo | None] = {}
        unavailable: dict[str, str] = {}  # service -> error type: Docker could not be read
        for n in names:  # one unreadable container (or no Docker at all) must not lose the rest
            try:
                infos[n] = docker_read.inspect_service(self.client, cfg, n)
            except Exception as e:  # noqa: BLE001  docker SDK/requests raise many types
                infos[n] = None
                unavailable[n] = type(e).__name__
                warnings.append(f"{n}: container state unavailable ({type(e).__name__})")
        secrets: set[str] = set()
        for i in infos.values():
            secrets |= secret_values(i.env) if i else set()
        out = _Items(secrets)

        for n in names:  # health: every service (a dependency that is down is evidence too)
            i = infos[n]
            if n in unavailable:
                htext = (
                    f"service {n}: container state unavailable "
                    f"(Docker read failed: {unavailable[n]})"
                )
            else:
                htext = _health_text(i) if i else f"service {n}: absent (no container)"
            out.add("health", n, htext, **_OBS_DOCKER)
        if (url := cfg.probes.get(service)) and (infos[service] is not None or unavailable):
            out.add("health", service, _probe(url, cfg.probe_timeout_s), **_OBS_PROBE)

        log_format: logs.LogFormat = "none"
        sick = [
            n
            for n in names
            if n != service
            and infos[n]
            and (infos[n].status != "running" or infos[n].health == "unhealthy")
        ]
        for n in [service, *sick]:
            if infos[n] is not None:
                lf = self._log_items(out, n, warnings, n == service)
                log_format = lf if n == service else log_format

        if infos[service]:
            for k, v in config_mod.effective_env(infos[service].env, cfg, secrets):
                out.add("config", service, f"{k}={v}", **_OBS_ENV)
        sf = config_mod.find_settings_file(cfg, service)
        if sf:
            try:
                src = (cfg.repo_root / sf).read_text("utf-8")
                ast.parse(src)  # declared_settings() hides a syntax error; surface it here
                declared = config_mod.declared_settings(src)
            except (OSError, UnicodeDecodeError, SyntaxError, ValueError) as e:
                declared = []
                warnings.append(f"{service}: settings source {sf} unreadable ({type(e).__name__})")
                where = f" at line {e.lineno}" if isinstance(e, SyntaxError) and e.lineno else ""
                out.add(
                    "config",
                    service,
                    f"settings source {sf} could not be read or parsed: {type(e).__name__}{where}",
                    path=sf,
                    line=e.lineno if isinstance(e, SyntaxError) and e.lineno else None,
                    **_DECLARED_SRC,
                )
            for name, decl, line in declared:
                out.add(
                    "config",
                    service,
                    f"settings.{name} {decl}",
                    path=sf,
                    line=line,
                    **_DECLARED_SRC,
                )

        for s in compose_mod.service_items(text, cfg, secrets):
            out.add(
                "compose",
                s.name,
                s.content,
                path=cfg.compose_file,
                line=s.line,
                **_DECLARED_COMPOSE,
            )

        base_sha = case.base_sha if case else git_head(cfg)
        bundle = EvidenceBundle(
            incident_id=incident_id, base_sha=base_sha, compose_sha256=compose_sha, items=out.items
        )
        return Collection(bundle, log_format, warnings)

    def _log_items(
        self, out: _Items, service: str, warnings: list[str], primary: bool
    ) -> logs.LogFormat:
        cfg = self.cfg
        try:
            raw = docker_read.read_logs(self.client, cfg, service)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"{service}: logs unavailable ({type(e).__name__})")
            out.add(
                "health",
                service,
                f"service {service}: logs unavailable (Docker read failed: {type(e).__name__})",
                **_OBS_DOCKER,
            )
            return "none"
        lines, cut = logs.window(
            raw, cfg.log_max_lines if primary else cfg.dependency_log_lines, cfg.log_max_bytes
        )
        if cut:
            warnings.append(
                f"{service}: log window truncated ({cfg.log_max_lines} lines/{cfg.log_max_bytes} B)"
            )
        recs = logs.group_records(lines)
        seen: set[tuple[str, int, str | None]] = set()
        for block in logs.make_blocks(recs, cfg.block_max_lines):
            ts: datetime | None = next((r.ts for r in block if r.ts), None)
            out.add("log", service, "\n".join(r.text for r in block), ts=ts)
            for r in block:
                for tb in r.tracebacks:
                    self._frame_items(out, service, tb.frames, r.ts, seen)
        return logs.detect_format(recs)

    def _frame_items(
        self, out: _Items, service: str, frames: list[Frame], ts: datetime | None, seen: set
    ) -> None:
        cfg = self.cfg
        ext = [f for f in frames if f.external]
        keep_ext = {id(f) for f in ext[-cfg.max_external_frames :]}
        for f in frames:
            if f.external and id(f) not in keep_ext:
                continue
            key = (f.path, f.line, f.function)
            if key in seen and f.exception is None:
                continue
            seen.add(key)
            repo_path = None if f.external else to_repo_path(f.path, service, cfg)
            body = ("[external] " if f.external else "") + f.text()
            keep_line = bool(repo_path) or f.external
            out.add(
                "trace_frame",
                service,
                body,
                path=repo_path,
                line=f.line if keep_line else None,
                ts=ts,
            )


def collect(incident_id: str, service: str, case: CaseManifest | None) -> EvidenceBundle:
    """Module-level `collect` with default config (lab project, proxy on 127.0.0.1:2375)."""
    return EvidenceCollector().collect(incident_id, service, case)


__all__ = ["Collection", "EvidenceCollector", "collect"]
