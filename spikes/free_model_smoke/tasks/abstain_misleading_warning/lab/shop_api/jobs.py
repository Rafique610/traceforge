"""Background jobs."""


def acquire_connection(settings):
    return object()


def run_job(job, settings):
    timeout = int(settings.get("JOB_TIMEOUT_S", "30"))
    conn = acquire_connection(settings)
    result = job["fn"](conn, timeout=timeout)
    return result
