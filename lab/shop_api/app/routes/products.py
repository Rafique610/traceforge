from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import catalog
from app.db import get_session
from app.schemas import ProductOut

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products(session: Session = Depends(get_session)):
    return catalog.list_products(session)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, session: Session = Depends(get_session)):
    product = catalog.get_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")
    return product
