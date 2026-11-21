from svc.ping_pong import ping


def pong(n):
    return ping(n - 1) if n else 0
