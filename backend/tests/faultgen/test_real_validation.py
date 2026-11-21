# ruff: noqa: E501
"""Real sandbox (Docker) validation of the repairable seed cases. Slow: 3x runs of 3 suites on 2 trees."""

import subprocess

import pytest

from traceforge.faultgen.validate import load_cases, validate_case


def _docker_up() -> bool:
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


pytestmark = [pytest.mark.docker, pytest.mark.skipif(not _docker_up(), reason="needs Docker")]


@pytest.mark.parametrize("cid", ["shop_api-001", "shop_api-002"])
def test_seed_case_is_red_green_and_stable(cid, datasets):
    case = next(c for c in load_cases(datasets) if c.manifest.case_id == cid)
    rep = validate_case(case, live=False)
    assert rep.passed, rep.problems
