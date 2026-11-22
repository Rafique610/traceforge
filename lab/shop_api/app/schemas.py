"""Request/response schemas. Constraints live here so bad input gets a 422."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    price: Decimal


class OrderItemIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=100)


class OrderIn(BaseModel):
    customer_email: str = Field(
        min_length=3, max_length=200, pattern=r"^[^@\s]+@[^@\s]+$"
    )
    items: list[OrderItemIn] = Field(min_length=1, max_length=50)


class OrderOut(BaseModel):
    id: int
    status: str
    total: Decimal


class QuoteOut(BaseModel):
    order_id: int
    subtotal: Decimal
    discount_pct: int
    goods: Decimal
    shipping: Decimal
    tax: Decimal
    grand_total: Decimal


class StockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    stock: int


class OrderTotalOut(BaseModel):
    order_id: int
    total: Decimal
    item_count: int
    average_unit_price: Decimal
    headline: str | None
