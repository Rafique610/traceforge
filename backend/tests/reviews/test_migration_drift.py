"""Alembic head must produce the same tables/columns as the ORM models (SQLite, no server)."""

from pathlib import Path

import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

from traceforge.database import Base
from traceforge.incidents import models as _i  # noqa: F401
from traceforge.repair import models as _r  # noqa: F401
from traceforge.reviews import models as _rv  # noqa: F401

BACKEND = Path(__file__).parents[2]


def test_migrations_match_models():
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:

        def upgrade(rev, _ctx):
            return script._upgrade_revs("head", rev)

        ctx = MigrationContext.configure(conn, opts={"fn": upgrade})
        with Operations.context(ctx):
            for step in script._upgrade_revs("head", ()):
                step.migration_fn()
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    cols = [d for d in diff if d[0] in ("add_table", "remove_table", "add_column", "remove_column")]
    assert not cols, cols
