"""Confirmation email rendering. The lab has no SMTP server: delivery is a log line."""

import logging

log = logging.getLogger("worker.emails")


def render_confirmation(order_id: int, total: str) -> str:
    return f"Your order #{order_id} is confirmed. Total charged: {total}."


def deliver(to: str, body: str) -> None:
    log.info("email to=%s body=%s", to, body)
