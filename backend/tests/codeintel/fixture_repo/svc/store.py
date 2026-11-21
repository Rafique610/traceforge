import os


def connect(host):
    return host, os.environ["EXTRA_KEY"]


def helper():
    return 1


class Store:
    def save(self, item=None) -> bool:
        return self._flush()

    def _flush(self):
        return True


class SubStore(Store):
    def again(self):
        return self.save()
