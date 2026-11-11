from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"],
                   dependencies=[Depends(require_roles("admin", "ops_manager"))])


@router.get("/summary")
def summary(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    return AnalyticsService(db).summary(days)


@router.get("/daily-volume")
def daily_volume(days: int = Query(14, ge=1, le=365), db: Session = Depends(get_db)):
    return AnalyticsService(db).daily_volume(days)


@router.get("/revenue-by-category")
def revenue(db: Session = Depends(get_db)):
    return AnalyticsService(db).revenue_by_category()


@router.get("/driver-performance")
def drivers(db: Session = Depends(get_db)):
    return AnalyticsService(db).driver_performance()


@router.get("/warehouse-performance")
def warehouses(db: Session = Depends(get_db)):
    return AnalyticsService(db).warehouse_performance()


@router.get("/vehicle-utilization")
def vehicles(db: Session = Depends(get_db)):
    return AnalyticsService(db).vehicle_utilization()
