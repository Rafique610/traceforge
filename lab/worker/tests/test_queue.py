"""Visible tests: queue consumption, retries, dead-lettering, heartbeat, connect retry."""

import json

import pytest
from worker import handlers, heartbeat, queue
from worker.models import Order
from worker.retry import with_backoff


def test_consume_one_job(redis_fake, factory, settings, job):
    redis_fake.lpush(settings.order_queue, job())
    taken = queue.consume_once(
        redis_fake, settings, lambda j: handlers.confirm_order(factory, j)
    )
    assert taken
    with factory() as s:
        o = s.get(Order, 1)
        assert o.status == "confirmed" and o.confirmed_at is not None


def test_empty_queue_returns_false(redis_fake, settings):
    assert queue.consume_once(redis_fake, settings, lambda j: None) is False


def test_confirm_is_idempotent(factory, job):
    j = json.loads(job())
    handlers.confirm_order(factory, j)
    handlers.confirm_order(factory, j)
    with factory() as s:
        assert s.get(Order, 1).status == "confirmed"


def test_failing_job_retries_three_times_then_dead_letters(redis_fake, settings, job):
    calls = []

    def boom(j):
        calls.append(1)
        raise RuntimeError("db down")

    redis_fake.lpush(settings.order_queue, job())
    queue.consume_once(redis_fake, settings, boom)
    assert len(calls) == 4  # first try + 3 retries
    dead = json.loads(redis_fake.lists[settings.dead_queue][0])
    assert dead["order_id"] == 1 and "RuntimeError" in dead["error"]


def test_unknown_order_is_dead_lettered(redis_fake, factory, settings, job):
    redis_fake.lpush(settings.order_queue, job(order_id=99))
    queue.consume_once(
        redis_fake, settings, lambda j: handlers.confirm_order(factory, j)
    )
    assert len(redis_fake.lists[settings.dead_queue]) == 1


def test_malformed_payload_is_dead_lettered(redis_fake, settings, job):
    redis_fake.lpush(settings.order_queue, "not json")
    assert queue.pop_job(redis_fake, settings) is None
    assert redis_fake.lists[settings.dead_queue] == ["not json"]


def test_backoff_delays_double():
    sleeps = []

    def fail():
        raise ValueError

    with pytest.raises(ValueError):
        with_backoff(fail, retries=3, base=1.0, sleep=sleeps.append)
    assert sleeps == [1.0, 2.0, 4.0]


def test_heartbeat_sets_key_with_15s_ttl(redis_fake):
    r = redis_fake
    heartbeat.beat(r)
    assert heartbeat.is_alive(r) and r.keys["worker:heartbeat"][1] == 15


def test_connect_retries_until_broker_is_up(settings, redis_fake):
    r = redis_fake
    r.ping_failures = 2
    assert (
        queue.connect_with_retry(settings, factory=lambda s: r, sleep=lambda s: None)
        is r
    )


def test_connect_gives_up_loudly(settings, redis_fake):
    r = redis_fake
    r.ping_failures = 999
    with pytest.raises(ConnectionError):
        queue.connect_with_retry(settings, factory=lambda s: r, sleep=lambda s: None)
