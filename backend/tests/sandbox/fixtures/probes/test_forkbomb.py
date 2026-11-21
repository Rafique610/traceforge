import os
import signal
import time


def test_fork_bomb_is_capped_by_pids_limit():
    kids = []
    try:
        for _ in range(2000):
            pid = os.fork()
            if pid == 0:
                time.sleep(30)
                os._exit(0)
            kids.append(pid)
        raise AssertionError("fork bomb was not stopped")
    except OSError:
        assert 0 < len(kids) < 2000
    finally:
        for k in kids:
            os.kill(k, signal.SIGKILL)
