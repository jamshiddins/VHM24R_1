from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from ..database import get_db
from ..auth import get_current_user
from ..models import User
from ..schemas import OrderFilters
from .. import crud

router = APIRouter()

@router.get("/summary")
async def get_analytics_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение краткой сводки аналитики"""
    try:
        analytics = crud.get_analytics_data(db, None, None, "day")
        return {
            "status": "success",
            "data": analytics.get("summary", {}),
            "total_orders": analytics.get("summary", {}).get("total_orders", 0),
            "total_revenue": analytics.get("summary", {}).get("total_revenue", 0.0)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "data": {
                "total_orders": 0,
                "total_revenue": 0.0,
                "avg_order_value": 0.0
            }
        }

@router.get("/")
async def get_analytics(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    group_by: str = "day",  # day, week, month
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение аналитических данных"""
    analytics = crud.get_analytics_data(db, date_from, date_to, group_by)
    return analytics

@router.get("/export")
async def export_analytics(
    format: str = Query("xlsx", regex="^(csv|xlsx)$"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Экспорт аналитического отчета"""
    from ..services.export_service import ExportService
    from fastapi.responses import StreamingResponse
    import io
    from datetime import datetime
    
    filters = OrderFilters(date_from=date_from, date_to=date_to)
    export_service = ExportService()
    
    try:
        exported_data = await export_service.export_analytics_report(db, filters, format)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"analytics_{timestamp}.{format}"
        
        mime_type = 'text/csv' if format == 'csv' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        
        return StreamingResponse(
            io.BytesIO(exported_data),
            media_type=mime_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
