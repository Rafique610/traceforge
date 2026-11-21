"""Order business logic: building orders and computing totals."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app import catalog
from app.models import Order, OrderItem
from app.pricing import ZERO, average_unit_price, line_total, money
from app.schemas import OrderIn


class UnknownProduct(LookupError):
    pass


def order_total(items: list[OrderItem]) -> Decimal:
    """Sum of price x quantity over all lines, rounded to 2 dp."""
    if not items:
        return ZERO
    total = ZERO
    for item in items:
        total += line_total(item.unit_price, item.quantity)
    return money(total)


def order_headline(items: list[OrderItem]) -> str | None:
    """Name of the first line, used in summaries and emails."""
    return items[0].product_name if items else None


def unit_count(items: list[OrderItem]) -> int:
    return sum(item.quantity for item in items)


def order_average_price(items: list[OrderItem]) -> Decimal:
    """Average price per unit; 0.00 for an order without lines."""
    return average_unit_price(order_total(items), unit_count(items)) if items else ZERO


def create_order(session: Session, payload: OrderIn) -> Order:
    """Persist a pending order with price snapshots. Raises UnknownProduct."""
    order = Order(customer_email=payload.customer_email, status="pending")
    for line in payload.items:
        product = catalog.get_product(session, line.product_id)
        if product is None:
            raise UnknownProduct(line.product_id)
        order.items.append(
            OrderItem(
                product_id=product.id,
                product_name=product.name,
                unit_price=product.price,
                quantity=line.quantity,
            )
        )
    session.add(order)
    session.commit()
    return order
