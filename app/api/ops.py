"""Warehouses, fleet, analytics."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..core.db import get_db
from ..core.cache import ttl_cache
from ..models import Warehouse, Vehicle, Shipment, Invoice, Role, User, TrackingEvent
from ..schemas import WarehouseCreate, VehicleCreate
from .deps import require_roles, audit

router = APIRouter(tags=["operations"])


@router.post("/warehouses", status_code=201)
def add_warehouse(b: WarehouseCreate, db: Session = Depends(get_db),
                  u: User = Depends(require_roles(Role.OPS_MANAGER, Role.WAREHOUSE_MANAGER))):
    w = Warehouse(**b.model_dump()); db.add(w); db.flush()
    audit(db, u, "create", "warehouse", w.name)
    return {"id": w.id}


@router.post("/warehouses/{wid}/receive/{tracking_no}")
def receive(wid: int, tracking_no: str, db: Session = Depends(get_db),
            u: User = Depends(require_roles(Role.WAREHOUSE_MANAGER))):
    # Row lock prevents two concurrent receives from overfilling capacity
    w = db.scalar(select(Warehouse).where(Warehouse.id == wid).with_for_update())
    sh = db.scalar(select(Shipment).where(Shipment.tracking_no == tracking_no))
    if not w or not sh:
        raise HTTPException(404, "Not found")
    if w.current_load >= w.capacity:
        raise HTTPException(409, "Warehouse at capacity")
    w.current_load += 1
    sh.warehouse_id = w.id
    audit(db, u, "receive", "warehouse", f"{w.id}:{tracking_no}")
    return {"load": w.current_load, "capacity": w.capacity,
            "capacity_alert": w.current_load / w.capacity >= 0.9}


@router.post("/vehicles", status_code=201)
def add_vehicle(b: VehicleCreate, db: Session = Depends(get_db),
                u: User = Depends(require_roles(Role.OPS_MANAGER, Role.DISPATCHER))):
    v = Vehicle(**b.model_dump()); db.add(v); db.flush()
    return {"id": v.id}


@router.post("/shipments/{tracking_no}/assign/{driver_id}")
def assign(tracking_no: str, driver_id: int, db: Session = Depends(get_db),
           u: User = Depends(require_roles(Role.DISPATCHER))):
    sh = db.scalar(select(Shipment).where(Shipment.tracking_no == tracking_no))
    drv = db.get(User, driver_id)
    if not sh or not drv or drv.role != Role.DRIVER.value:
        raise HTTPException(404, "Shipment or driver not found")
    sh.driver_id = driver_id
    audit(db, u, "assign", "shipment", f"{tracking_no}->{driver_id}")
    return {"ok": True}


@ttl_cache("analytics")
def _summary():
    from ..core.db import SessionLocal
    db = SessionLocal()
    try:
        total = db.scalar(select(func.count(Shipment.id))) or 0
        by = dict(db.execute(select(Shipment.status, func.count()).group_by(Shipment.status)).all())
        rev = dict(db.execute(select(Shipment.category, func.sum(Invoice.total))
                              .join(Invoice, Invoice.shipment_id == Shipment.id)
                              .group_by(Shipment.category)).all())
        attempted = by.get("delivered", 0) + by.get("failed_delivery", 0) + by.get("returned", 0)
        pct = lambda n: round(100 * n / total, 2) if total else 0
        return {"total_shipments": total, "by_status": by,
                "delivery_success_rate": round(100 * by.get("delivered", 0) / attempted, 2) if attempted else 0,
                "failed_delivery_rate": pct(by.get("failed_delivery", 0)),
                "return_rate": pct(by.get("returned", 0)),
                "delayed": by.get("delayed", 0),
                "revenue_by_category": {k: float(v) for k, v in rev.items()}}
    finally:
        db.close()


@router.get("/analytics/summary")
def summary(u: User = Depends(require_roles(Role.OPS_MANAGER))):
    return _summary()


@router.get("/analytics/daily-volume")
def daily_volume(db: Session = Depends(get_db),
                 u: User = Depends(require_roles(Role.OPS_MANAGER))):
    rows = db.execute(select(func.date(Shipment.created_at), func.count())
                      .group_by(func.date(Shipment.created_at))).all()
    return [{"date": str(d), "shipments": c} for d, c in rows]


@router.get("/analytics/avg-delivery-time")
def avg_delivery_time(db: Session = Depends(get_db),
                      u: User = Depends(require_roles(Role.OPS_MANAGER))):
    rows = db.execute(select(Shipment.created_at, TrackingEvent.created_at)
                      .join(TrackingEvent, TrackingEvent.shipment_id == Shipment.id)
                      .where(TrackingEvent.status == "delivered")).all()
    if not rows:
        return {"delivered": 0, "avg_hours": 0}
    hours = [(done - start).total_seconds() / 3600 for start, done in rows]
    return {"delivered": len(hours), "avg_hours": round(sum(hours) / len(hours), 4)}


@router.get("/analytics/driver-performance")
def driver_performance(db: Session = Depends(get_db),
                       u: User = Depends(require_roles(Role.OPS_MANAGER))):
    rows = db.execute(select(Shipment.driver_id, Shipment.status, func.count())
                      .where(Shipment.driver_id.is_not(None))
                      .group_by(Shipment.driver_id, Shipment.status)).all()
    out = {}
    for driver, status, count in rows:
        out.setdefault(str(driver), {})[status] = count
    return out