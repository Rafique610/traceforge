"""The worker's view of the shared `orders` table (the API owns the schema)."""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_email: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
