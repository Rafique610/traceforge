"""BugsInPy converter (P5-S05): parsing and gold-symbol mapping on real inputs, no network."""

from pathlib import Path

from traceforge.contracts.case_manifest import CaseManifest
from traceforge.external import bugsinpy as b
from traceforge.sandbox import images
from traceforge.sandbox.config import SandboxConfig

REPO = Path(__file__).resolve().parents[2]
# the real BugsInPy fastapi bug 5 fix (bug_patch.txt), verbatim
FASTAPI_5 = """diff --git a/fastapi/utils.py b/fastapi/utils.py
index a068cc5..6a0c1bf 100644
--- a/fastapi/utils.py
+++ b/fastapi/utils.py
@@ -97,7 +97,7 @@ def create_cloned_field(field: ModelField) -> ModelField:
             original_type.__name__, __config__=original_type.__config__
         )
         for f in original_type.__fields__.values():
-            use_type.__fields__[f.name] = f
+            use_type.__fields__[f.name] = create_cloned_field(f)
         use_type.__validators__ = original_type.__validators__
     if PYDANTIC_1:
         new_field = ModelField(
"""


def test_bug_info_and_run_test_parse():
    info = b.parse_info('python_version="3.8.3"\nbuggy_commit_id="766157b"\ntest_file="tests/a.py"')
    assert info == {
        "python_version": "3.8.3",
        "buggy_commit_id": "766157b",
        "test_file": "tests/a.py",
    }
    sh = "pytest tests/test_filter_pydantic_sub_model.py::test_filter_sub_model\n"
    assert b.failing_tests(sh) == ["tests/test_filter_pydantic_sub_model.py::test_filter_sub_model"]


def test_requirements_drop_project_and_tooling_and_pin_our_pytest():
    reqs = b.requirements(
        "﻿aiofiles==0.5.0\nfastapi==0.55.1\nblack==19.10b0\npydantic==1.5.1\npytest==5.4.3\n"
    )
    assert reqs.split() == ["aiofiles==0.5.0", "pydantic==1.5.1", "pytest==8.3.4"]


def test_changed_lines_on_a_real_fix():
    assert b.changed_lines(FASTAPI_5) == {"fastapi/utils.py": {100}}


def test_gold_symbol_is_the_innermost_def_around_the_change():
    patch = (REPO / "datasets/cases/shop_api-011/mutation.patch").read_text("utf-8")
    (g,) = b.gold_symbols(REPO, patch, "x")
    assert (g.qualname, g.start_line, g.end_line) == ("quote", 12, 35)  # matches the dev manifest


def test_manifest_accepts_a_bugsinpy_case():
    c = CaseManifest(
        case_id="bugsinpy-fastapi-5", split="test", cause_class="application_code",
        fault_family="bugsinpy", service="fastapi", base_sha="abc", distance=0,
        gold_symbols=[
            {"path": "lab/fastapi/fastapi/utils.py", "qualname": "f",
             "start_line": 1, "end_line": 2},
        ],
        reproducer_id="datasets/reproducers/bugsinpy-fastapi-5/test_symptom.py::t",
        hidden_test_ids=["datasets/hidden_tests/bugsinpy-fastapi-5/test_hidden_behaviour.py::t"],
        variant_group="bugsinpy:fastapi-5", origin="bugsinpy",
    )  # fmt: skip
    assert c.service == "fastapi"


def test_default_image_tag_is_unchanged_and_base_image_changes_it():
    default = SandboxConfig()
    assert images.dockerfile(default) == images.DOCKERFILE.read_text("utf-8")
    old = SandboxConfig(base_image="python:3.8-slim")
    assert "FROM python:3.8-slim\n" in images.dockerfile(old)
    assert images.image_tag(old) != images.image_tag(default)
