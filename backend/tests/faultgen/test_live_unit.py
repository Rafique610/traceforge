"""Live-check plumbing that needs no Docker: probe table and the DB env-file mapping."""

from traceforge.faultgen import live


def test_supported_services_have_valid_probes():
    assert set(live.CHECKS) == {"lab_redis", "lab_db"}
    for code, ok, failed in live.CHECKS.values():
        compile(code, "probe", "exec")
        assert ok in code and failed in code


def test_db_env_file_maps_lab_names_to_app_names(tmp_path):
    lab = tmp_path / "lab"
    lab.mkdir()
    (lab / ".env").write_text("# lab\nLAB_DB_USER=shop\nLAB_DB_PASSWORD=pw\nLAB_DB_NAME=shopdb\n")
    out = (tmp_path / "out").mkdir() or tmp_path / "out"
    text = open(live._db_env_file(lab, out), encoding="utf-8").read()
    assert text.splitlines() == [
        "DB_USER=shop",
        "DB_PASSWORD=pw",
        "DB_NAME=shopdb",
        "DB_HOST=lab_db",
    ]


def test_unsupported_stop_is_reported_not_run(tmp_path):
    assert "supports one of" in live.live_runtime_check(["worker"], tmp_path)[0]
