from app import settings

SERVER = ("cache", 6379)


class Client:
    def __init__(self, host, port):
        if (host, port) != SERVER:
            raise ConnectionError(f"cannot reach host {host!r} port {port}")
        self.data = {}

    def set(self, key, value):
        self.data[key] = value
        return True


def connect():
    return Client(settings.CACHE_HOST, settings.CACHE_PORT)
