"""Catalogue reads (all product DB access)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product


def list_products(session: Session) -> list[Product]:
    return list(session.scalars(select(Product).order_by(Product.id)))


def get_product(session: Session, product_id: int) -> Product | None:
    return session.get(Product, product_id)
