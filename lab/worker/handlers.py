"""Job handlers. `confirm_order` marks the order confirmed and emails the customer."""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from worker import emails
from worker.models import Order

log = logging.getLogger("worker.handlers")


class OrderNotFound(LookupError):
    pass


def confirm_order(factory: sessionmaker[Session], job: dict) -> None:
    """Idempotent: a job for an already confirmed order is a no-op."""
    with factory() as session:
        order = session.get(Order, job["order_id"])
        if order is None:
            raise OrderNotFound(job["order_id"])
        if order.status == "confirmed":
            return
        order.status = "confirmed"
        order.confirmed_at = datetime.now(UTC).replace(tzinfo=None)
        session.commit()
        emails.deliver(
            order.customer_email, emails.render_confirmation(order.id, job["total"])
        )
    log.info("confirmed order %s", job["order_id"])
