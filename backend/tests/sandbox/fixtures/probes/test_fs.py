import os
from pathlib import Path

import pytest


def test_cannot_write_worktree():
    with pytest.raises(OSError):
        Path("/work/evil.txt").write_text("x")


def test_cannot_write_rootfs():
    for p in ("/etc/evil", "/usr/evil", "/evil"):
        with pytest.raises(OSError):
            Path(p).write_text("x")


def test_tmp_is_writable_scratch():
    Path("/tmp/ok.txt").write_text("x")


def test_not_root_no_socket_no_host_files():
    assert os.getuid() != 0
    for p in (
        "/var/run/docker.sock",
        "/run/docker.sock",
        "/run/desktop",
        "/mnt/host",
        "/host_mnt",
        "/hidden",
    ):
        assert not os.path.exists(p), p
    assert not any(Path("/home").iterdir())
    assert not os.access("/root", os.R_OK)
    # GPG_KEY is the public key id baked into the python base image, not a credential
    secret_like = [
        k
        for k in os.environ
        if k != "GPG_KEY" and any(w in k.upper() for w in ("TOKEN", "SECRET", "KEY", "PASSWORD"))
    ]
    assert secret_like == []
