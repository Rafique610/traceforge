"""Exceptions shared by the runner and real-sources run function.

Kept in their own module so `python -m traceforge.evaluation.runner` (where the runner is
`__main__`) and `real_run` see the same class object."""


class StopRun(RuntimeError):
    """Raise from run_fn on provider outage: stop cleanly; rerun with the same run_id resumes."""
