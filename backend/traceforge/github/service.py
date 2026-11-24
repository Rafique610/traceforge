"""Create an incident from a GitHub issue. Issue text is untrusted data, never instructions."""

import hashlib
import re

from sqlalchemy.orm import Session

from traceforge.config import Settings
from traceforge.contracts.evidence import EvidenceItem
from traceforge.github import client
from traceforge.github.client import GitHubError
from traceforge.github.schemas import GitHubIntake, GitHubIntakeOut
from traceforge.incidents import repository
from traceforge.incidents.models import EvidenceItemRow, Incident
from traceforge.incidents.service import _event
from traceforge.incidents.states import State

MAX_CONTENT = 20_000
_SECRETS = [
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.S
    ),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key)(\s*[:=]\s*)\S+"),
]


def redact(text: str) -> str:
    for pat in _SECRETS:
        text = pat.sub(
            lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]" if m.lastindex == 2 else "[REDACTED]",
            text,
        )
    return text


def _service(data: dict, requested: str | None) -> str:
    if requested:
        return requested
    for label in data.get("labels") or []:
        name = label.get("name", "") if isinstance(label, dict) else str(label)
        if name.startswith("service:") and len(name) > 8:
            return name[8:][:128]
    raise GitHubError(422, "service required: pass `service` or label the issue service:<name>")


def create_from_github(db: Session, body: GitHubIntake, settings: Settings) -> GitHubIntakeOut:
    owner, repo, number = client.parse_issue_url(body.url)
    if not client.is_allowed(owner, repo, settings.github_allowed_owners):
        raise GitHubError(422, "repository is not in the GitHub allowlist")
    data = client.fetch_issue(owner, repo, number, settings)  # raises before any DB write
    if "pull_request" in data:
        raise GitHubError(422, "url is a pull request, not an issue")
    service = _service(data, body.service)
    title = redact(str(data.get("title") or ""))[:10_000]
    if not title.strip():
        raise GitHubError(502, "GitHub issue has no title")
    text = redact(str(data.get("body") or ""))
    content = f"UNTRUSTED github issue {owner}/{repo}#{number}\n\n{title}\n\n{text}"[:MAX_CONTENT]
    item = EvidenceItem(
        id="EV-0001",
        kind="issue",
        service=service,
        content=content,
        sha256=hashlib.sha256(content.encode()).hexdigest(),
    )
    incident = repository.add_incident(
        db, Incident(service=service, symptom=title, source="github", state=State.CREATED)
    )
    payload = {"github_issue": f"{owner}/{repo}#{number}"}
    repository.add_event(db, _event(incident.id, "system", "created", None, State.CREATED, payload))
    db.add(
        EvidenceItemRow(
            incident_id=incident.id, **item.model_dump(exclude={"scope", "basis", "origin"})
        )
    )
    db.commit()
    return GitHubIntakeOut(incident=incident, evidence_id=item.id, evidence_sha256=item.sha256)
