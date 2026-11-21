from svc import pong_mod


def ping(n):
    return pong_mod.pong(n - 1) if n else 0
