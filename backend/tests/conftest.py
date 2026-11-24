import pytest

from traceforge.agent import axforge, beatapi


@pytest.fixture(autouse=True)
def _providers_start_open(monkeypatch, tmp_path_factory):
    """The first-failure halts are per process: every test starts with both providers open, and the
    real AxForge request spacing is switched off (tests that check it set it themselves)."""
    monkeypatch.setattr(axforge, "MIN_START_INTERVAL_S", 0.0)
    monkeypatch.setattr(  # never the real shared pacing state of the machine
        axforge, "PACING_FILE", tmp_path_factory.mktemp("pacing") / "axforge_pacing.json"
    )
    axforge.reset_halt()
    beatapi.reset_halt()
    yield
    axforge.reset_halt()
    beatapi.reset_halt()


@pytest.fixture(autouse=True)
def _slot2_marker_isolated(tmp_path, monkeypatch):
    """Tests never read the real runs/axforge_keys_verified.json (it enables key slot 2 and its
    pacing jitter in the real repository). Tests that need slot 2 set their own marker."""
    from traceforge.agent import axforge

    monkeypatch.setattr(axforge, "ENABLE_MARKER", tmp_path / "no_keys_verified.json")
