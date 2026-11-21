import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).parents[2]


def test_alembic_offline_sql_creates_new_tables():
    out = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert out.returncode == 0, out.stderr[-500:]
    for t in ("patches", "validation_runs", "reviews"):
        assert f"CREATE TABLE {t}" in out.stdout
    assert "JSONB" in out.stdout
