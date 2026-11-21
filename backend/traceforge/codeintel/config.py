"""Graph vocabulary and tunable weights. Weights live ONLY here (tune on dev split only)."""

from dataclasses import dataclass, field

# Forward edge type -> reverse edge type (D23). Reverse edges are stored with reverse=True.
REVERSE_OF: dict[str, str] = {
    "calls": "called_by",
    "imports": "imported_by",
    "reads_config": "read_by",
    "defined_in": "defines",
    "tests_covers": "covered_by",
    "declares_config": "declared_by",
    "service_env": "env_of",
    "service_runs": "run_by",
    "depends_on": "required_by",
}
FORWARD_TYPES = tuple(REVERSE_OF)
UNKNOWN_PREFIX = "unknown:"
SOURCES = ("ast", "compose", "settings", "dotenv")

# Never produce an UNKNOWN edge for these attribute names (builtin container/str/file methods).
COMMON_METHODS = frozenset(
    "get items keys values append extend update pop add remove clear copy join split strip "
    "format read write close open send recv sort index count insert encode decode startswith "
    "endswith lower upper replace find setdefault discard union intersection".split()
)
SKIP_DIRS = frozenset(
    ".git .venv venv env node_modules __pycache__ .cache .mypy_cache .pytest_cache .ruff_cache "
    "dist build site-packages .tox .next .idea .vscode".split()
)


@dataclass(frozen=True)
class GraphConfig:
    # Larger = stronger/closer. Config binding > call (limits report). Tune on dev split only.
    edge_weights: dict[str, float] = field(
        default_factory=lambda: {
            "reads_config": 1.0,
            "declares_config": 0.9,
            "service_env": 0.9,
            "service_runs": 0.7,
            "defined_in": 0.6,
            "calls": 0.6,
            "depends_on": 0.5,
            "tests_covers": 0.4,
            "imports": 0.3,
        }
    )
    unknown_confidence: float = 0.2
    # Edge types walked by distance() (structural defined_in/imports and tests excluded).
    distance_edge_types: tuple[str, ...] = (
        "calls",
        "reads_config",
        "declares_config",
        "service_env",
        "service_runs",
        "depends_on",
    )
    hub_degree_threshold: int = 12  # above this, hub_factor shrinks as threshold/degree
    max_neighbor_hops: int = 2
    impact_max_depth: int = 3
    max_file_bytes: int = 1_000_000
