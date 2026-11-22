import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import coupons, inventory, orders
from app.db import get_session
from app.models import Order
from app.queue import OrderQueue, get_queue
from app.quote import quote
from app.schemas import OrderIn, OrderOut, OrderTotalOut, QuoteOut

logger = logging.getLogger("app.orders")
router = APIRouter(prefix="/orders", tags=["orders"])


def _load(session: Session, order_id: int) -> Order:
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    return order


@router.post("", response_model=OrderOut, status_code=201)
def create_order(
    payload: OrderIn,
    session: Session = Depends(get_session),
    queue: OrderQueue = Depends(get_queue),
):
    try:
        order = orders.create_order(session, payload)
    except orders.UnknownProduct as exc:
        raise HTTPException(status_code=404, detail=f"product {exc} not found") from exc
    except inventory.OutOfStock as exc:
        logger.warning("order rejected: %s", exc)
        raise HTTPException(status_code=409, detail="not enough stock") from exc
    total = orders.order_total(order.items)
    try:
        queue.enqueue_confirmation(order.id, total)
    except Exception as exc:  # broker unreachable: order stays pending
        logger.exception("order %s confirmation enqueue failed", order.id)
        raise HTTPException(status_code=503, detail="order queue unavailable") from exc
    return OrderOut(id=order.id, status=order.status, total=total)


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, session: Session = Depends(get_session)):
    order = _load(session, order_id)
    return OrderOut(
        id=order.id, status=order.status, total=orders.order_total(order.items)
    )


@router.get("/{order_id}/total", response_model=OrderTotalOut)
def get_order_total(order_id: int, session: Session = Depends(get_session)):
    order = _load(session, order_id)
    return OrderTotalOut(
        order_id=order.id,
        total=orders.order_total(order.items),
        item_count=orders.unit_count(order.items),
        average_unit_price=orders.order_average_price(order.items),
        headline=orders.order_headline(order.items),
    )


@router.get("/{order_id}/quote", response_model=QuoteOut)
def get_order_quote(
    order_id: int, coupon: str | None = None, session: Session = Depends(get_session)
):
    order = _load(session, order_id)
    try:
        q = quote(order.items, coupon)
    except coupons.UnknownCoupon as exc:
        raise HTTPException(status_code=404, detail="unknown coupon") from exc
    except coupons.ExpiredCoupon as exc:
        raise HTTPException(status_code=410, detail="coupon expired") from exc
    return QuoteOut(order_id=order.id, **q)
