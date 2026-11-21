"""Idempotent seed: inserts a few products when the catalogue is empty.

Run: python -m app.seed
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_engine
from app.models import Base, Product

PRODUCTS = [
    ("Espresso beans 1kg", Decimal("18.50")),
    ("Ceramic mug", Decimal("7.25")),
    ("Pour-over kettle", Decimal("42.00")),
    ("Paper filters x100", Decimal("3.99")),
]


def seed(session: Session) -> int:
    if session.scalars(select(Product).limit(1)).first() is not None:
        return 0
    session.add_all(Product(name=n, price=p) for n, p in PRODUCTS)
    session.commit()
    return len(PRODUCTS)


if __name__ == "__main__":
    engine = get_engine()
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        print(f"seeded {seed(s)} products")
