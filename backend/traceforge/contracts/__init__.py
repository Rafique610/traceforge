"""The five data shapes exchanged between Track A and Track B. See README "Changing a contract"."""

from traceforge.contracts.agent_run import AgentRunRecord, Diagnosis
from traceforge.contracts.case_manifest import CaseManifest, CauseClass, GoldSymbol
from traceforge.contracts.context import ContextBundle, ContextHit
from traceforge.contracts.evidence import EvidenceBundle, EvidenceItem
from traceforge.contracts.test_run import TestOutcome, TestRunRequest, TestRunResult

CONTRACTS = {
    "case_manifest": CaseManifest,
    "evidence_bundle": EvidenceBundle,
    "context_bundle": ContextBundle,
    "test_run_request": TestRunRequest,
    "test_run_result": TestRunResult,
    "agent_run_record": AgentRunRecord,
}

__all__ = [
    "CONTRACTS",
    "AgentRunRecord",
    "CaseManifest",
    "CauseClass",
    "ContextBundle",
    "ContextHit",
    "Diagnosis",
    "EvidenceBundle",
    "EvidenceItem",
    "GoldSymbol",
    "TestOutcome",
    "TestRunRequest",
    "TestRunResult",
]
