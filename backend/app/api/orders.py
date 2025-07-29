from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from ..database import get_db
from ..auth import get_current_user
from ..models import User
from ..schemas import OrderFilters
from .. import crud

router = APIRouter()

@router.get("/")
async def get_orders(
    page: int = 1,
    page_size: int = 50,
    order_number: Optional[str] = None,
    machine_code: Optional[str] = None,
    payment_type: Optional[str] = None,
    match_status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    change_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение списка заказов с фильтрами"""
    filters = OrderFilters(
        order_number=order_number,
        machine_code=machine_code,
        payment_type=payment_type,
        match_status=match_status,
        date_from=date_from,
        date_to=date_to,
        change_type=change_type
    )
    
    orders, total = crud.get_orders_with_filters(db, filters, page, page_size)
    
    return {
        "orders": orders,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size
        }
    }

@router.get("/{order_id}/changes")
async def get_order_changes(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение истории изменений заказа"""
    order = crud.order_crud.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    changes = crud.order_change_crud.get_changes_by_order(db, order_id)
    return {
        "order": order,
        "changes": changes
    }

@router.get("/by-number/{order_number}")
async def get_order_versions(
    order_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение всех версий заказа по номеру"""
    versions = crud.get_order_versions(db, order_number)
    if not versions:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {"versions": versions}
