"""Price quote for an order: subtotal -> coupon -> shipping -> tax -> grand total."""

from datetime import date

from app import coupons, shipping
from app.models import OrderItem
from app.orders import order_total
from app.pricing import money
from app.settings import Settings, get_settings


def quote(items: list[OrderItem], coupon: str | None = None, today: date | None = None,
          settings: Settings | None = None) -> dict:
    s = settings or get_settings()
    subtotal = order_total(items)
    pct = 0
    if coupon:
        pct = coupons.discount_pct(
            coupon,
            coupons.parse_codes(s.coupon_codes),
            s.max_discount_pct,
            coupons.valid_until(s.coupons_valid_until),
            today or date.today(),
        )
    goods = coupons.apply_discount(subtotal, pct)
    ship = shipping.shipping_fee(goods, s.shipping_fee, s.free_shipping_over)
    tax = shipping.tax_amount(goods, s.tax_rate)
    return {
        "subtotal": subtotal,
        "discount_pct": pct,
        "goods": goods,
        "shipping": ship,
        "tax": tax,
        "grand_total": money(goods + ship + tax),
    }
