import pytest

from traceforge.regression.experiment import (
    ADR_PATH,
    ExperimentSpec,
    PreregistrationError,
    adr_decision,
    validate_preregistration,
)
from traceforge.regression.retrieval_adapters import (
    RetrievalAdapter,
    available_arms,
    get_adapter,
)


def adr(tmp_path, decision, status="ACCEPTED"):
    p = tmp_path / "adr.md"
    p.write_text(f"# ADR\n\nStatus: {status}\n\n## Decision\n{decision}\n\n## Consequences\n- x\n")
    return p


def spec(tmp_path, **kw):
    d = dict(name="s11", arms=["RET-L", "RET-G"], hypotheses=["H1"], case_ids=["c1"], seed=7,
             replicates=2, token_ceiling=50000, budget_approved_by="owner", budget_approved_on="2026-12-01",
             run_dir=str(tmp_path / "runs" / "new"))  # fmt: skip
    return ExperimentSpec(**{**d, **kw})


def test_real_adr_is_not_go_so_runs_are_refused():
    assert adr_decision(ADR_PATH)[0] == "none"
    with pytest.raises(PreregistrationError) as e:
        validate_preregistration(ExperimentSpec(name="x", arms=["RET-L"]))
    assert any("ADR 0003" in r for r in e.value.reasons)


@pytest.mark.parametrize(
    "text,want", [("**None yet.** later", "none"), ("**Go**: H1 and H2 hold", "go"),
                  ("Decision: no-go", "no-go"), ("No-go. option A", "no-go")],
)  # fmt: skip
def test_adr_parsing(tmp_path, text, want):
    assert adr_decision(adr(tmp_path, text))[0] == want


def test_go_and_budget_allows_start(tmp_path):
    validate_preregistration(spec(tmp_path), adr(tmp_path, "**Go**: ok"))


def test_no_budget_refused_even_when_go(tmp_path):
    with pytest.raises(PreregistrationError) as e:
        validate_preregistration(spec(tmp_path, token_ceiling=0, budget_approved_by=""), adr(tmp_path, "Go"))
    assert any("token budget" in r for r in e.value.reasons)


def test_other_refusals(tmp_path):
    a = adr(tmp_path, "Go")
    with pytest.raises(PreregistrationError) as e:
        validate_preregistration(
            spec(tmp_path, arms=["RET-ZZ"], hypotheses=[], case_ids=["c1"], excluded_case_ids=["c1"], run_dir="results/final/x"), a
        )
    t = " ".join(e.value.reasons)
    assert "RET-ZZ" in t and "hypotheses" in t and "analysed sites" in t and "results/final" in t


def test_registry_placeholders_and_optional_arms_absent():
    arms = available_arms()
    assert {"RET-L", "RET-G"} <= set(arms) and "RET-E" not in arms and "RET-LGE" not in arms
    a = get_adapter("RET-G")
    assert isinstance(a, RetrievalAdapter) and a.mode == "G" and get_adapter("RET-L").mode == "L"
    with pytest.raises(KeyError):
        get_adapter("RET-E")
