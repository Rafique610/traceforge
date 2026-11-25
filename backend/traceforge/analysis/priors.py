# ruff: noqa: E501
"""Fixed priors and budgets for the P5-S12 overlay traversal and ranker.

These numbers are fixed BEFORE any scored run (preregistration in
docs/research/rootcause-impact-evaluation.md records the sha256 of this file). They are not tuned
on any evaluation data. Change = new preregistration.
"""

from __future__ import annotations

EVIDENCE_CLASSES = ("static", "observed", "inferred", "unknown")
STATIC_MIN_CONFIDENCE = 0.85  # edge confidence >= this is `static`; below is `inferred`

# Edge-type prior (how much a hop of this type is trusted as a dependency/causal link).
EDGE_PRIOR: dict[str, float] = {
    "calls": 1.0, "called_by": 0.8,
    "imports": 0.4, "imported_by": 0.3,
    "reads_config": 1.0, "read_by": 0.7,
    "inherits": 0.7, "subclassed_by": 0.6,
    "overrides": 0.7, "overridden_by": 0.6,
    "tests_covers": 0.6, "covered_by": 0.5,
    "env_of": 0.9, "declared_by": 0.9, "defined_in": 0.5,
}  # fmt: skip

# Direction groups (design section 3 table).
FORWARD_TYPES = ("calls", "imports", "reads_config", "inherits", "overrides")
REVERSE_TYPES = ("called_by", "imported_by", "read_by", "subclassed_by", "overridden_by")
CONFIG_TYPES = ("reads_config", "env_of", "declared_by", "defined_in")
TEST_TYPES = ("covered_by",)

# Ranking-only multipliers per direction group (root causes are mostly upstream of the symptom).
DIRECTION_PRIOR = {"forward": 1.0, "config": 1.0, "reverse": 0.5, "tests": 0.2}
KIND_PRIOR = {"function": 1.0, "method": 1.0, "class": 0.8, "config_key": 1.0}
SEED_PRIOR = {"frame": 1.0, "failing_test": 0.8, "symptom": 0.7, "retrieval": 0.6}
INNER_FRAME_BOOST = 1.0  # deepest non-test frame; other frames use 0.8
OUTER_FRAME = 0.8
UNDECLARED_KEY_BOOST = 1.25  # key read by code, set by no compose service (structure only)
NAME_TOKEN_MATCH = 0.5  # symptom word equals a token of a config key name

# Traversal budgets.
DEPTH = {"forward": 3, "reverse": 2, "config": 2, "tests": 1}  # ranker
IMPACT_DEPTH = 3  # P5-S15 dependants
DECAY = 0.75  # multiplied in once per hop (so a one-hop cause scores below its seed)
TOP_N_PER_HOP = 12
NODE_CAP = 150
EDGE_TYPE_BUDGET = 60  # max nodes accepted through one edge type per traversal
HUB_STOP_DEGREE = 12  # degree_all above this is not expanded unless seed or named
NAME_RESOLVE_MAX = 4  # unknown `x.name()` call resolved by name to at most this many methods
NAME_RESOLVE_CONF = 0.4  # confidence of a name-resolved (inferred) call edge
