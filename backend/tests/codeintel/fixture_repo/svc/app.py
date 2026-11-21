from . import store
from .settings import LOG_X, Settings, get_cfg
from .store import Store, connect


def run():
    cfg = get_cfg()
    client = connect(cfg.redis_host)
    handle(client, cfg.pool)
    return Settings().log_level, LOG_X


def handle(client, pool):
    s = Store()
    s.save()
    store.helper()
    return client, pool


def dispatch(handlers, name):
    return handlers[name]()


def plugin(obj, name):
    return getattr(obj, name)()


def inject(callback):
    return callback(1)


def ping(repo):
    return repo.save()
