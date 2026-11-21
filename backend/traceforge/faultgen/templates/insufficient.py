# ruff: noqa: E501
"""insufficient_evidence: an intermittent symptom whose cause cannot be determined from the evidence.

The service logs are withheld (`logs: suppressed` in runtime.yaml, log_format "none") and the shop API
contract is silent on why the worker heartbeat may lapse. Expected answer: abstain.
"""

from traceforge.faultgen.model import CaseDraft
from traceforge.faultgen.templates.api_stub import api_conftest

REPRODUCER = '''"""Reproducer: the health endpoint intermittently reports the worker as missing."""


def test_health_degraded_when_worker_heartbeat_lapses(client, queue):
    assert client.get("/health").status_code == 200
    queue.alive = False
    r = client.get("/health")
    assert r.status_code == 503
    assert r.json()["worker"] == "missing"
'''


def make(case_id: str, service: str = "shop_api") -> CaseDraft:
    return CaseDraft(
        case_id=case_id,
        cause_class="insufficient_evidence",
        fault_family="intermittent_no_logs",
        service=service,
        variant_group="insufficient:worker_heartbeat_lapse",
        log_format="none",
        distance=None,
        template="insufficient.suppressed_logs",
        params={},
        reproducer_files={"conftest.py": api_conftest(), "test_symptom.py": REPRODUCER},
        runtime={"logs": "suppressed", "symptom": "intermittent"},
        notes="no cause is determinable: logs withheld, contract silent on heartbeat lapses",
    )
