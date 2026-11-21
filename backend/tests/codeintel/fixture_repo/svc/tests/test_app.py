from svc import store
from svc.app import run


def test_run():
    run()


def test_store_save():
    s = store.Store()
    s.save()
