"""Job queue client used by the worker and the API to send order emails."""

import socket

from settings import settings


def connect():
    cfg = settings()
    info = socket.getaddrinfo(cfg.redis_host, cfg.redis_port, type=socket.SOCK_STREAM)
    return info[0][4]


def enqueue(job_name, payload):
    address = connect()
    return {"queued": job_name, "to": address, "payload": payload}


def send_order_email(order_id):
    return enqueue("order_email", {"order_id": order_id})
